"""AI Use Case 3: Contract Renewal & Savings Opportunity Detection (Deliverable D-09)."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ..config import CONTRACT_RENEWAL_WARNING_DAYS, VOLUME_MILESTONES
from ..etl.load import read_table


def contract_renewal_alerts(engine=None) -> pd.DataFrame:
    """Contracts expiring within the renewal warning window."""
    contracts = read_table("contracts", engine)
    contracts["end_date"] = pd.to_datetime(contracts["end_date"])
    today = pd.Timestamp(datetime.utcnow().date())

    contracts["days_to_expiry"] = (contracts["end_date"] - today).dt.days
    due = contracts[
        (contracts["days_to_expiry"] <= CONTRACT_RENEWAL_WARNING_DAYS)
        & (contracts["status"] == "ACTIVE")
    ].copy()
    due["priority"] = due["days_to_expiry"].apply(
        lambda d: "HIGH" if d <= 30 else ("MEDIUM" if d <= 60 else "LOW")
    )
    due["recommendation"] = due.apply(
        lambda r: (
            f"Contract {r['contract_id']} expires in {int(r['days_to_expiry'])} days "
            f"(current discount {r['negotiated_discount_pct']}%). Begin renegotiation now to "
            "lock in or improve terms before lapse."
        ),
        axis=1,
    )
    return due.sort_values("days_to_expiry").reset_index(drop=True)


def volume_milestone_opportunities(engine=None) -> pd.DataFrame:
    """Suppliers approaching a volume milestone that should trigger renegotiation."""
    spend = read_table("spend_transactions", engine)
    by_supplier = (
        spend.groupby(["supplier_id", "supplier_name"], as_index=False)["amount"].sum()
        .rename(columns={"amount": "total_spend"})
    )

    rows = []
    for _, row in by_supplier.iterrows():
        spend_amt = row["total_spend"]
        passed = [m for m in VOLUME_MILESTONES if spend_amt >= m]
        next_milestones = [m for m in VOLUME_MILESTONES if spend_amt < m]
        if not passed:
            continue
        current_milestone = passed[-1]
        next_milestone = next_milestones[0] if next_milestones else None
        gap_to_next = round(next_milestone - spend_amt, 2) if next_milestone else None

        rows.append({
            "supplier_id": row["supplier_id"],
            "supplier_name": row["supplier_name"],
            "total_spend": round(float(spend_amt), 2),
            "milestone_reached": current_milestone,
            "next_milestone": next_milestone,
            "gap_to_next_milestone": gap_to_next,
            "recommendation": (
                f"{row['supplier_name']} has crossed the Rs {current_milestone:,.0f} spend milestone "
                f"(Rs {spend_amt:,.0f} YTD). This volume typically qualifies for improved pricing - "
                "trigger a renegotiation review."
            ),
        })

    return pd.DataFrame(rows).sort_values("total_spend", ascending=False).reset_index(drop=True)


def savings_summary(engine=None) -> dict:
    renewals = contract_renewal_alerts(engine)
    milestones = volume_milestone_opportunities(engine)
    return {
        "contract_renewal_alerts": renewals.to_dict("records"),
        "volume_milestone_opportunities": milestones.to_dict("records"),
        "renewal_alert_count": int(len(renewals)),
        "milestone_opportunity_count": int(len(milestones)),
    }
