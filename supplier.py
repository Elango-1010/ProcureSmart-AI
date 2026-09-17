"""Supplier Analytics (Deliverable D-05)."""
from __future__ import annotations

import pandas as pd

from ..etl.load import read_table
from ..etl.transform import normalise_supplier_name


def _load(engine=None):
    spend = read_table("spend_transactions", engine)
    suppliers = read_table("suppliers", engine)
    return spend, suppliers


def preferred_supplier_utilisation(spend: pd.DataFrame, suppliers: pd.DataFrame) -> pd.DataFrame:
    """% of category spend going to the preferred (contracted) supplier per category."""
    preferred_ids = set(suppliers.loc[suppliers["is_preferred"].astype(bool), "supplier_id"])
    df = spend.copy()
    df["is_preferred_spend"] = df["supplier_id"].isin(preferred_ids)

    grouped = df.groupby("category").apply(
        lambda g: pd.Series({
            "total_spend": g["amount"].sum(),
            "preferred_spend": g.loc[g["is_preferred_spend"], "amount"].sum(),
        }),
        include_groups=False,
    ).reset_index()
    grouped["preferred_utilisation_pct"] = round(
        100 * grouped["preferred_spend"] / grouped["total_spend"], 2
    )
    return grouped.sort_values("preferred_utilisation_pct").reset_index(drop=True)


def supplier_concentration(spend: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Herfindahl-style concentration: what share of total spend sits with the top N suppliers."""
    by_supplier = (
        spend.groupby(["supplier_id", "supplier_name"], as_index=False)["amount"].sum()
        .sort_values("amount", ascending=False)
    )
    total = by_supplier["amount"].sum()
    top = by_supplier.head(top_n)
    return pd.DataFrame([{
        "top_n": top_n,
        "top_n_spend": round(float(top["amount"].sum()), 2),
        "total_spend": round(float(total), 2),
        "concentration_pct": round(100 * top["amount"].sum() / total, 2) if total else 0.0,
        "top_suppliers": top["supplier_name"].tolist(),
    }])


def detect_duplicate_suppliers(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Flag supplier records that normalise to the same canonical name.

    This is what catches 'Nexa Technologies Pvt Ltd' / 'NEXA TECHNOLOGIES PVT. LTD.'
    / 'Nexa Tech Pvt Ltd' as the same vendor under three IDs.
    """
    df = suppliers.copy()
    df["normalised_name"] = df["supplier_name"].map(normalise_supplier_name)
    dupes = df[df.duplicated("normalised_name", keep=False)].sort_values("normalised_name")
    groups = []
    for name, group in dupes.groupby("normalised_name"):
        groups.append({
            "canonical_name": name,
            "supplier_ids": group["supplier_id"].tolist(),
            "name_variants": group["supplier_name"].tolist(),
            "duplicate_count": len(group),
        })
    return pd.DataFrame(groups)


def contract_compliance(spend: pd.DataFrame) -> pd.DataFrame:
    """Compliance rate per department - share of spend that is on-contract."""
    df = spend.copy()
    df["on_contract"] = df["contract_status"] == "ON_CONTRACT"
    grouped = df.groupby("department").apply(
        lambda g: pd.Series({
            "total_spend": g["amount"].sum(),
            "on_contract_spend": g.loc[g["on_contract"], "amount"].sum(),
        }),
        include_groups=False,
    ).reset_index()
    grouped["compliance_pct"] = round(
        100 * grouped["on_contract_spend"] / grouped["total_spend"], 2
    )
    return grouped.sort_values("compliance_pct").reset_index(drop=True)


def supplier_analytics_summary(engine=None) -> dict:
    spend, suppliers = _load(engine)
    return {
        "preferred_supplier_utilisation": preferred_supplier_utilisation(spend, suppliers).to_dict("records"),
        "supplier_concentration_top5": supplier_concentration(spend, 5).to_dict("records")[0],
        "duplicate_suppliers": detect_duplicate_suppliers(suppliers).to_dict("records"),
        "contract_compliance_by_department": contract_compliance(spend).to_dict("records"),
    }
