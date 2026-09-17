"""Spend Analytics (Deliverable D-04).

Reads from the unified spend_transactions table and produces the analytics
the RFP requires: total spend, department/category/supplier breakdowns,
and monthly/quarterly trends.
"""
from __future__ import annotations

import pandas as pd

from ..etl.load import read_table


def _load_spend(engine=None) -> pd.DataFrame:
    df = read_table("spend_transactions", engine)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def total_spend(df: pd.DataFrame | None = None, engine=None) -> float:
    df = df if df is not None else _load_spend(engine)
    return round(float(df["amount"].sum()), 2)


def spend_by_department(df: pd.DataFrame | None = None, engine=None) -> pd.DataFrame:
    df = df if df is not None else _load_spend(engine)
    out = (
        df.groupby("department", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "total_spend"})
        .sort_values("total_spend", ascending=False)
    )
    out["pct_of_total"] = round(100 * out["total_spend"] / out["total_spend"].sum(), 2)
    return out.reset_index(drop=True)


def spend_by_category(df: pd.DataFrame | None = None, engine=None) -> pd.DataFrame:
    df = df if df is not None else _load_spend(engine)
    out = (
        df.groupby("category", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "total_spend"})
        .sort_values("total_spend", ascending=False)
    )
    out["pct_of_total"] = round(100 * out["total_spend"] / out["total_spend"].sum(), 2)
    return out.reset_index(drop=True)


def spend_by_supplier(df: pd.DataFrame | None = None, engine=None, top_n: int = 15) -> pd.DataFrame:
    df = df if df is not None else _load_spend(engine)
    out = (
        df.groupby(["supplier_id", "supplier_name"], as_index=False)["amount"]
        .agg(total_spend="sum", transaction_count="count")
        .sort_values("total_spend", ascending=False)
        .head(top_n)
    )
    return out.reset_index(drop=True)


def monthly_trend(df: pd.DataFrame | None = None, engine=None) -> pd.DataFrame:
    df = df if df is not None else _load_spend(engine)
    out = df.copy()
    out["month"] = out["transaction_date"].dt.to_period("M").astype(str)
    trend = out.groupby("month", as_index=False)["amount"].sum().rename(columns={"amount": "total_spend"})
    return trend.sort_values("month").reset_index(drop=True)


def quarterly_trend(df: pd.DataFrame | None = None, engine=None) -> pd.DataFrame:
    df = df if df is not None else _load_spend(engine)
    out = df.copy()
    out["quarter"] = out["transaction_date"].dt.to_period("Q").astype(str)
    trend = out.groupby("quarter", as_index=False)["amount"].sum().rename(columns={"amount": "total_spend"})
    return trend.sort_values("quarter").reset_index(drop=True)


def contract_status_breakdown(df: pd.DataFrame | None = None, engine=None) -> pd.DataFrame:
    """Split of on-contract / off-contract / no-contract spend - feeds maverick KPI."""
    df = df if df is not None else _load_spend(engine)
    out = (
        df.groupby("contract_status", as_index=False)["amount"]
        .agg(total_spend="sum", transaction_count="count")
    )
    out["pct_of_total"] = round(100 * out["total_spend"] / out["total_spend"].sum(), 2)
    return out.sort_values("total_spend", ascending=False).reset_index(drop=True)


def off_contract_spend_pct(df: pd.DataFrame | None = None, engine=None) -> float:
    """Off-contract spend % KPI - a named KPI in the approved proposal."""
    df = df if df is not None else _load_spend(engine)
    total = df["amount"].sum()
    off = df.loc[df["contract_status"] != "ON_CONTRACT", "amount"].sum()
    return round(100 * off / total, 2) if total else 0.0


def spend_summary(engine=None) -> dict:
    """Single call returning the full analytics summary - used by the API and dashboard."""
    df = _load_spend(engine)
    return {
        "total_spend": total_spend(df),
        "transaction_count": int(len(df)),
        "by_department": spend_by_department(df).to_dict("records"),
        "by_category": spend_by_category(df).to_dict("records"),
        "top_suppliers": spend_by_supplier(df).to_dict("records"),
        "monthly_trend": monthly_trend(df).to_dict("records"),
        "quarterly_trend": quarterly_trend(df).to_dict("records"),
        "contract_status_breakdown": contract_status_breakdown(df).to_dict("records"),
        "off_contract_spend_pct": off_contract_spend_pct(df),
    }
