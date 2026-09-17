"""Budget Monitoring & Procurement KPI Dashboard (part of D-04/D-05)."""
from __future__ import annotations

import pandas as pd

from ..etl.load import read_table


def budget_utilisation(engine=None) -> pd.DataFrame:
    """Department-level budget consumption against allocated budget."""
    spend = read_table("spend_transactions", engine)
    budgets = read_table("department_budgets", engine)

    actual = spend.groupby("department", as_index=False)["amount"].sum().rename(
        columns={"amount": "actual_spend"}
    )
    merged = budgets.merge(actual, on="department", how="left")
    merged["actual_spend"] = merged["actual_spend"].fillna(0.0)
    merged["utilisation_pct"] = round(
        100 * merged["actual_spend"] / merged["allocated_budget"], 2
    )
    merged["remaining_budget"] = merged["allocated_budget"] - merged["actual_spend"]
    merged["threshold_breached"] = merged["utilisation_pct"] >= 90.0
    return merged.sort_values("utilisation_pct", ascending=False).reset_index(drop=True)


def procurement_kpis(engine=None) -> dict:
    """Core KPI dashboard figures named in the approved proposal."""
    spend = read_table("spend_transactions", engine)
    requisitions = read_table("requisitions", engine)

    total_spend = float(spend["amount"].sum())
    off_contract = spend.loc[spend["contract_status"] != "ON_CONTRACT", "amount"].sum()

    decided = requisitions[requisitions["status"].isin(["APPROVED", "REJECTED"])]
    approval_rate = round(
        100 * (decided["status"] == "APPROVED").sum() / max(len(decided), 1), 2
    )

    by_supplier = spend.groupby(["supplier_id", "supplier_name"], as_index=False)["amount"].sum()
    top_supplier = by_supplier.sort_values("amount", ascending=False).iloc[0]

    return {
        "total_spend": round(total_spend, 2),
        "off_contract_spend_pct": round(100 * off_contract / total_spend, 2) if total_spend else 0.0,
        "requisition_approval_rate_pct": approval_rate,
        "pending_requisitions": int((requisitions["status"] == "PENDING").sum()),
        "top_supplier_by_spend": top_supplier["supplier_name"],
        "top_supplier_spend": round(float(top_supplier["amount"]), 2),
        "total_transactions": int(len(spend)),
        "total_requisitions": int(len(requisitions)),
    }
