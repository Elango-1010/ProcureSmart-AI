"""AI Use Case 2: Supplier Consolidation Recommendation (Deliverable D-09)."""
from __future__ import annotations

import pandas as pd

from ..etl.load import read_table


def consolidation_opportunities(engine=None, min_suppliers: int = 2) -> pd.DataFrame:
    """Identify categories served by multiple suppliers and recommend consolidation.

    For each such category, recommends consolidating spend onto the supplier
    that already has the best negotiated position (preferred + highest current
    share), with the estimated leverage gain from moving off-preferred spend.
    """
    spend = read_table("spend_transactions", engine)
    suppliers = read_table("suppliers", engine)
    contracts = read_table("contracts", engine)

    sup_lookup = suppliers.set_index("supplier_id")
    rows = []

    for category, group in spend.groupby("category"):
        by_supplier = group.groupby(["supplier_id", "supplier_name"], as_index=False)["amount"].sum()
        if by_supplier["supplier_id"].nunique() < min_suppliers:
            continue

        by_supplier = by_supplier.sort_values("amount", ascending=False)
        total_category_spend = by_supplier["amount"].sum()

        preferred_ids = set(
            suppliers.loc[(suppliers["category"] == category) & (suppliers["is_preferred"].astype(bool)), "supplier_id"]
        )
        recommended = by_supplier[by_supplier["supplier_id"].isin(preferred_ids)]
        recommended_row = recommended.iloc[0] if len(recommended) else by_supplier.iloc[0]

        fragmented_spend = total_category_spend - recommended_row["amount"]
        fragmented_pct = round(100 * fragmented_spend / total_category_spend, 2) if total_category_spend else 0.0

        discount = contracts.loc[contracts["supplier_id"] == recommended_row["supplier_id"], "negotiated_discount_pct"]
        discount_pct = float(discount.iloc[0]) if len(discount) else 5.0
        estimated_savings = round(fragmented_spend * (discount_pct / 100), 2)

        supplier_count = by_supplier["supplier_id"].nunique()
        message = (
            f"{supplier_count} suppliers currently serve the {category} category with overlapping "
            f"pricing. Consolidating the Rs {fragmented_spend:,.0f} ({fragmented_pct}% of category spend) "
            f"currently spread across non-preferred vendors onto {recommended_row['supplier_name']} could "
            f"unlock an estimated Rs {estimated_savings:,.0f} in negotiation leverage, based on that "
            f"supplier's existing {discount_pct:.1f}% contracted discount."
        )

        rows.append({
            "category": category,
            "supplier_count": supplier_count,
            "total_category_spend": round(float(total_category_spend), 2),
            "recommended_supplier": recommended_row["supplier_name"],
            "fragmented_spend": round(float(fragmented_spend), 2),
            "fragmented_pct": fragmented_pct,
            "estimated_savings": estimated_savings,
            "recommendation": message,
        })

    return pd.DataFrame(rows).sort_values("estimated_savings", ascending=False).reset_index(drop=True)
