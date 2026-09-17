"""Synthetic enterprise procurement dataset generator.

Generates the three procurement domains required by the RFP:
  1. Spend data      (ERP exports, corporate card, invoices)
  2. Requisitions
  3. Supplier contracts

Patterns are deliberately seeded so the AI layer has genuine signals to find:
  - Maverick spend       : off-contract purchases from non-preferred suppliers
  - Consolidation        : multiple suppliers serving one category
  - Volume milestones    : suppliers approaching renegotiation thresholds
  - Duplicate suppliers  : same vendor under name variants
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import CATEGORIES, DEPARTMENTS, RAW_DIR, ensure_dirs

SEED = 42
FISCAL_START = date(2025, 4, 1)
FISCAL_END = date(2026, 3, 31)

# Duplicate-supplier variants deliberately planted for detection
DUPLICATE_VARIANTS = {
    "Nexa Technologies Pvt Ltd": ["Nexa Technologies", "NEXA TECHNOLOGIES PVT. LTD.", "Nexa Tech Pvt Ltd"],
    "Orion Office Supplies": ["Orion Office Supplies Ltd", "ORION OFFICE SUPPLIES"],
}

SUPPLIER_POOL = {
    "IT Hardware": ["Nexa Technologies Pvt Ltd", "Zenith Computing", "BluePeak Systems", "Arcadia IT Traders"],
    "IT Software & Licences": ["Cloudspan Software", "Vertex Licensing", "Meridian Softworks"],
    "Office Supplies": ["Orion Office Supplies", "Paperline Traders", "Kanban Stationers"],
    "Professional Services": ["Sterling Advisory", "Cobalt Consulting", "Adept Partners"],
    "Travel": ["Skyroute Travel", "Voyager Corporate Travel"],
    "Facilities Maintenance": ["Prime Facility Care", "GreenEdge Services", "Urban Upkeep"],
    "Marketing Services": ["Lumen Creative", "BrightArc Media", "Pulse Marketing Co"],
    "Logistics & Freight": ["Transcore Logistics", "FleetBridge Cargo"],
}


def _rng():
    random.seed(SEED)
    np.random.seed(SEED)


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def build_suppliers() -> pd.DataFrame:
    """Supplier master data. First supplier per category is the preferred one."""
    rows = []
    idx = 1
    for category, names in SUPPLIER_POOL.items():
        for position, name in enumerate(names):
            rows.append({
                "supplier_id": f"SUP{idx:04d}",
                "supplier_name": name,
                "category": category,
                "is_preferred": position == 0,
                "onboarded_date": _random_date(date(2021, 1, 1), date(2024, 6, 30)),
                "country": "India",
            })
            idx += 1

    # Plant duplicate-name variants as separate supplier records
    for canonical, variants in DUPLICATE_VARIANTS.items():
        base = next(r for r in rows if r["supplier_name"] == canonical)
        for variant in variants:
            rows.append({
                "supplier_id": f"SUP{idx:04d}",
                "supplier_name": variant,
                "category": base["category"],
                "is_preferred": False,
                "onboarded_date": _random_date(date(2023, 1, 1), date(2025, 6, 30)),
                "country": "India",
            })
            idx += 1

    return pd.DataFrame(rows)


def build_contracts(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Contracts exist only for preferred suppliers - everything else is off-contract."""
    rows = []
    preferred = suppliers[suppliers["is_preferred"]]
    for i, (_, sup) in enumerate(preferred.iterrows(), start=1):
        start = _random_date(date(2024, 4, 1), date(2025, 6, 30))
        # Deliberately let a few contracts expire inside the renewal warning window
        term_days = 365 if i % 3 else 300
        rows.append({
            "contract_id": f"CTR{i:04d}",
            "supplier_id": sup["supplier_id"],
            "category": sup["category"],
            "start_date": start,
            "end_date": start + timedelta(days=term_days),
            "contracted_value": float(random.choice([800_000, 1_200_000, 2_000_000, 3_000_000])),
            "negotiated_discount_pct": round(random.uniform(4.0, 14.0), 2),
            "status": "ACTIVE",
        })
    return pd.DataFrame(rows)


def _category_base_amount(category: str) -> float:
    bands = {
        "IT Hardware": (25_000, 180_000),
        "IT Software & Licences": (15_000, 120_000),
        "Office Supplies": (2_000, 25_000),
        "Professional Services": (40_000, 250_000),
        "Travel": (8_000, 90_000),
        "Facilities Maintenance": (10_000, 70_000),
        "Marketing Services": (20_000, 160_000),
        "Logistics & Freight": (12_000, 95_000),
    }
    low, high = bands.get(category, (5_000, 60_000))
    return float(round(np.random.uniform(low, high), 2))


def build_spend(suppliers: pd.DataFrame, contracts: pd.DataFrame, n: int = 5200) -> pd.DataFrame:
    """Generate the spend fact table across three source systems."""
    contract_by_supplier = dict(zip(contracts["supplier_id"], contracts["contract_id"]))
    sup_records = suppliers.to_dict("records")
    by_category: dict[str, list] = {}
    for rec in sup_records:
        by_category.setdefault(rec["category"], []).append(rec)

    sources = ["ERP_EXPORT", "CORPORATE_CARD", "INVOICE_SYSTEM"]
    rows = []

    for i in range(1, n + 1):
        category = random.choice(CATEGORIES)
        pool = by_category.get(category, sup_records)

        # 72% of spend routes to the preferred supplier; the rest is leakage
        preferred = [s for s in pool if s["is_preferred"]]
        if preferred and random.random() < 0.72:
            supplier = preferred[0]
        else:
            supplier = random.choice(pool)

        contract_id = contract_by_supplier.get(supplier["supplier_id"])
        if contract_id:
            contract_status = "ON_CONTRACT"
        elif any(s["is_preferred"] for s in pool):
            contract_status = "OFF_CONTRACT"   # a contract existed but was bypassed
        else:
            contract_status = "NO_CONTRACT"

        amount = _category_base_amount(category)
        source = random.choices(sources, weights=[0.6, 0.15, 0.25])[0]

        # Corporate card spend is smaller and far more likely to be off-contract
        if source == "CORPORATE_CARD":
            amount = round(amount * random.uniform(0.15, 0.45), 2)
            if random.random() < 0.55 and contract_status == "ON_CONTRACT":
                alt = [s for s in pool if not s["is_preferred"]]
                if alt:
                    supplier = random.choice(alt)
                    contract_id, contract_status = None, "OFF_CONTRACT"

        rows.append({
            "transaction_id": f"TXN{i:06d}",
            "source_system": source,
            "supplier_id": supplier["supplier_id"],
            "supplier_name": supplier["supplier_name"],
            "category": category,
            "department": random.choice(DEPARTMENTS),
            "amount": amount,
            "currency": "INR",
            "contract_id": contract_id,
            "contract_status": contract_status,
            "requisition_id": f"REQ{random.randint(1, 900):05d}" if random.random() < 0.55 else None,
            "transaction_date": _random_date(FISCAL_START, FISCAL_END),
        })

    df = pd.DataFrame(rows)

    # --- Seed explicit maverick-spend outliers (high value, off contract) ---
    maverick_idx = df.sample(n=45, random_state=SEED).index
    df.loc[maverick_idx, "amount"] = np.random.uniform(320_000, 850_000, size=len(maverick_idx)).round(2)
    df.loc[maverick_idx, "contract_status"] = "OFF_CONTRACT"
    df.loc[maverick_idx, "contract_id"] = None

    # --- Seed data-quality defects for the QA / validation layer to catch ---
    dirty = df.sample(n=60, random_state=7).index
    df.loc[dirty[:20], "category"] = None                    # missing category
    df.loc[dirty[20:35], "department"] = "  it  "            # whitespace + casing
    df.loc[dirty[35:50], "amount"] = -abs(df.loc[dirty[35:50], "amount"])  # negative amounts
    df.loc[dirty[50:], "supplier_name"] = df.loc[dirty[50:], "supplier_name"].str.upper()

    # --- Seed exact duplicate rows ---
    duplicates = df.sample(n=25, random_state=11).copy()
    df = pd.concat([df, duplicates], ignore_index=True)

    return df


def build_requisitions(suppliers: pd.DataFrame, n: int = 900) -> pd.DataFrame:
    """Requisition domain, including pending items for the portal to action."""
    requesters = [
        "A. Krishnan", "M. Fernandes", "S. Balaji", "R. Iyer", "P. Menon",
        "N. Sharma", "D. Rao", "K. Subramanian", "V. Joseph", "T. Ahmed",
    ]
    sup_records = suppliers.to_dict("records")
    rows = []
    for i in range(1, n + 1):
        category = random.choice(CATEGORIES)
        pool = [s for s in sup_records if s["category"] == category] or sup_records
        supplier = random.choice(pool)
        amount = _category_base_amount(category)

        if i > n - 120:
            status, approver, decided = "PENDING", None, None
        else:
            status = random.choices(
                ["APPROVED", "REJECTED", "PENDING"], weights=[0.74, 0.11, 0.15]
            )[0]
            approver = random.choice(requesters) if status != "PENDING" else None
            decided = None

        rows.append({
            "requisition_id": f"REQ{i:05d}",
            "requester": random.choice(requesters),
            "department": random.choice(DEPARTMENTS),
            "category": category,
            "requested_supplier_id": supplier["supplier_id"],
            "estimated_amount": amount,
            "justification": f"Procurement request for {category.lower()} - operational requirement.",
            "status": status,
            "approver": approver,
            "decided_at": decided,
        })
    return pd.DataFrame(rows)


def build_budgets() -> pd.DataFrame:
    rows = []
    for dept in DEPARTMENTS:
        rows.append({
            "department": dept,
            "fiscal_year": "FY2025-26",
            "allocated_budget": float(random.choice([4_000_000, 6_000_000, 9_000_000, 12_000_000])),
        })
    return pd.DataFrame(rows)


def generate_all(n_spend: int = 5200) -> dict[str, pd.DataFrame]:
    """Generate every raw dataset and write it to data/raw as CSV."""
    _rng()
    ensure_dirs()

    suppliers = build_suppliers()
    contracts = build_contracts(suppliers)
    spend = build_spend(suppliers, contracts, n=n_spend)
    requisitions = build_requisitions(suppliers)
    budgets = build_budgets()

    datasets = {
        "suppliers": suppliers,
        "contracts": contracts,
        "spend": spend,
        "requisitions": requisitions,
        "budgets": budgets,
    }

    # Spend is split across three source files to mimic fragmented systems
    for source in spend["source_system"].unique():
        subset = spend[spend["source_system"] == source]
        subset.to_csv(RAW_DIR / f"spend_{source.lower()}.csv", index=False)

    suppliers.to_csv(RAW_DIR / "suppliers.csv", index=False)
    contracts.to_csv(RAW_DIR / "contracts.csv", index=False)
    requisitions.to_csv(RAW_DIR / "requisitions.csv", index=False)
    budgets.to_csv(RAW_DIR / "budgets.csv", index=False)

    return datasets


if __name__ == "__main__":
    data = generate_all()
    print("Generated raw procurement datasets in", RAW_DIR)
    for name, frame in data.items():
        print(f"  {name:<14} {len(frame):>6} rows")
