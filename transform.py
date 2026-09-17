"""Transform stage - cleaning, standardisation and validation.

Every function here is pure (DataFrame in, DataFrame out) so the QA layer can
unit-test each rule in isolation.
"""
from __future__ import annotations

import re

import pandas as pd

from ..schema import UNIFIED_SPEND_COLUMNS

LEGAL_SUFFIXES = [
    r"\bpvt\.?\s*ltd\.?\b", r"\bprivate\s+limited\b", r"\bltd\.?\b",
    r"\blimited\b", r"\binc\.?\b", r"\bllp\b", r"\bco\.?\b", r"\bcorp\.?\b",
]


def normalise_supplier_name(name: str | None) -> str:
    """Strip casing, punctuation and legal suffixes so vendor variants collapse.

    'NEXA TECHNOLOGIES PVT. LTD.' and 'Nexa Technologies' both become
    'nexa technologies' - which is how duplicate suppliers are detected.
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = str(name).lower().strip()
    for suffix in LEGAL_SUFFIXES:
        text = re.sub(suffix, " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def standardise_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Trim and title-case department/category; fill missing categories."""
    out = df.copy()
    for col in ("department", "category"):
        if col in out.columns:
            out[col] = (
                out[col].astype("string").str.strip().str.title()
            )
    if "category" in out.columns:
        out["category"] = out["category"].fillna("Uncategorised")
    if "department" in out.columns:
        out["department"] = out["department"].fillna("Unassigned")
    return out


def clean_amounts(df: pd.DataFrame, column: str = "amount") -> pd.DataFrame:
    """Coerce amounts to numeric and convert credit notes to absolute values.

    Negative amounts in procurement feeds are typically credits/reversals; they
    are flagged rather than silently dropped so nothing disappears unexplained.
    """
    out = df.copy()
    out[column] = pd.to_numeric(out[column], errors="coerce")
    out["is_credit_note"] = out[column] < 0
    out[column] = out[column].abs()
    out = out[out[column].notna()]
    return out


def deduplicate(df: pd.DataFrame, key: str = "transaction_id") -> pd.DataFrame:
    """Drop exact duplicate records on the business key, keeping the first."""
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=[key], keep="first").reset_index(drop=True)
    out.attrs["duplicates_removed"] = before - len(out)
    return out


def enrich_contract_status(spend: pd.DataFrame, contracts: pd.DataFrame) -> pd.DataFrame:
    """Recompute contract status from the contracts table rather than trusting source."""
    out = spend.copy()
    active = set(contracts.loc[contracts["status"] == "ACTIVE", "supplier_id"])
    contract_lookup = dict(zip(contracts["supplier_id"], contracts["contract_id"]))
    contracted_categories = set(contracts["category"])

    def status_for(row) -> str:
        if row["supplier_id"] in active:
            return "ON_CONTRACT"
        if row.get("category") in contracted_categories:
            return "OFF_CONTRACT"
        return "NO_CONTRACT"

    out["contract_status"] = out.apply(status_for, axis=1)
    out["contract_id"] = out["supplier_id"].map(contract_lookup)
    return out


def conform_to_unified_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee the unified column contract, in order."""
    out = df.copy()
    for col in UNIFIED_SPEND_COLUMNS:
        if col not in out.columns:
            out[col] = None
    keep = UNIFIED_SPEND_COLUMNS + [
        c for c in ("normalised_supplier", "is_credit_note") if c in out.columns
    ]
    out = out[keep]
    out["transaction_date"] = pd.to_datetime(out["transaction_date"], errors="coerce").dt.date
    return out


def transform_spend(spend: pd.DataFrame, contracts: pd.DataFrame) -> pd.DataFrame:
    """Full spend transform pipeline."""
    df = standardise_text_fields(spend)
    df = clean_amounts(df)
    df["normalised_supplier"] = df["supplier_name"].map(normalise_supplier_name)
    df = enrich_contract_status(df, contracts)
    df = deduplicate(df, key="transaction_id")
    removed = df.attrs.get("duplicates_removed", 0)
    out = conform_to_unified_schema(df)
    out.attrs["duplicates_removed"] = removed
    return out


def transform_suppliers(suppliers: pd.DataFrame) -> pd.DataFrame:
    out = suppliers.copy()
    out["normalised_name"] = out["supplier_name"].map(normalise_supplier_name)
    out["is_preferred"] = out["is_preferred"].astype(bool)
    return out


def validate_spend(df: pd.DataFrame) -> dict:
    """Data-quality report used by the QA layer and governance dashboard."""
    total = len(df)
    issues = {
        "total_rows": total,
        "missing_supplier": int(df["supplier_id"].isna().sum()),
        "missing_category": int((df["category"] == "Uncategorised").sum()),
        "missing_department": int((df["department"] == "Unassigned").sum()),
        "null_amounts": int(df["amount"].isna().sum()),
        "zero_amounts": int((df["amount"] == 0).sum()),
        "duplicate_ids": int(df["transaction_id"].duplicated().sum()),
        "duplicates_removed": int(df.attrs.get("duplicates_removed", 0)),
        "invalid_dates": int(pd.isna(pd.to_datetime(df["transaction_date"], errors="coerce")).sum()),
    }
    defects = sum(
        v for k, v in issues.items()
        if k not in ("total_rows", "duplicates_removed")
    )
    issues["completeness_pct"] = round(100 * (1 - defects / max(total, 1)), 2)
    issues["schema_columns_present"] = all(c in df.columns for c in UNIFIED_SPEND_COLUMNS)
    return issues
