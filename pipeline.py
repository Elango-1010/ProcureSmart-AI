"""ETL orchestration - the end-to-end spend data integration pipeline.

Run with:  python -m src.etl.pipeline
"""
from __future__ import annotations

import time

from ..config import PROCESSED_DIR, ensure_dirs
from ..governance.catalogue import GovernanceCatalogue
from ..schema import get_engine, init_db
from . import extract, load, transform


def run_pipeline(engine=None, verbose: bool = True) -> dict:
    """Execute the full integration pipeline and return a run summary."""
    started = time.time()
    ensure_dirs()
    engine = engine or get_engine()
    init_db(engine)
    catalogue = GovernanceCatalogue(engine)

    # ---------- EXTRACT ----------
    spend_raw = extract.extract_spend_sources()
    suppliers_raw = extract.extract_table("suppliers")
    contracts_raw = extract.extract_table("contracts")
    requisitions_raw = extract.extract_table("requisitions")
    budgets_raw = extract.extract_table("budgets")

    source_asset_ids = []
    for file_name in extract.list_source_files():
        asset_id = catalogue.register(
            name=file_name,
            asset_type="SOURCE_FILE",
            source_system=file_name.replace("spend_", "").replace(".csv", "").upper(),
            transformation="Raw ingest - no transformation applied",
            classification="CONFIDENTIAL" if "spend" in file_name else "INTERNAL",
        )
        source_asset_ids.append(asset_id)

    spend_source_ids = [
        catalogue.register(name=f, asset_type="SOURCE_FILE")
        for f in extract.list_source_files() if f.startswith("spend_")
    ]

    # ---------- TRANSFORM ----------
    suppliers = transform.transform_suppliers(suppliers_raw)
    spend = transform.transform_spend(spend_raw, contracts_raw)
    quality = transform.validate_spend(spend)

    # ---------- LOAD ----------
    counts = {
        "spend_transactions": load.load_frame(spend, "spend_transactions", engine),
        "suppliers": load.load_frame(suppliers, "suppliers", engine),
        "contracts": load.load_frame(contracts_raw, "contracts", engine),
        "requisitions": load.load_frame(requisitions_raw, "requisitions", engine),
        "department_budgets": load.load_frame(budgets_raw, "department_budgets", engine),
    }

    # ---------- GOVERNANCE ----------
    spend_table_id = catalogue.register(
        name="spend_transactions",
        asset_type="TABLE",
        source_system="ProcureSmart DB",
        row_count=counts["spend_transactions"],
        upstream=spend_source_ids,
        transformation=(
            "Standardise text fields; coerce and absolutise amounts; normalise supplier "
            "names; recompute contract status from contracts table; deduplicate on "
            "transaction_id; conform to unified spend schema"
        ),
        classification="CONFIDENTIAL",
    )
    supplier_table_id = catalogue.register(
        name="suppliers", asset_type="TABLE", source_system="ProcureSmart DB",
        row_count=counts["suppliers"], upstream=[source_asset_ids[0]],
        transformation="Supplier name normalisation for duplicate detection",
    )
    contract_table_id = catalogue.register(
        name="contracts", asset_type="TABLE", source_system="ProcureSmart DB",
        row_count=counts["contracts"], upstream=[source_asset_ids[0]],
        transformation="Direct load with schema conformance",
    )
    catalogue.register(
        name="requisitions", asset_type="TABLE", source_system="ProcureSmart DB",
        row_count=counts["requisitions"], upstream=[source_asset_ids[0]],
        transformation="Direct load with schema conformance",
    )
    catalogue.register(
        name="department_budgets", asset_type="TABLE", source_system="ProcureSmart DB",
        row_count=counts["department_budgets"], upstream=[source_asset_ids[0]],
        transformation="Direct load",
    )
    catalogue.register(
        name="vw_category_spend", asset_type="DERIVED_VIEW",
        row_count=counts["spend_transactions"],
        upstream=[spend_table_id, supplier_table_id, contract_table_id],
        transformation="Aggregation of spend by category, supplier and contract status",
    )

    catalogue.log_action(
        "PIPELINE", "etl_run", "EXECUTED", actor="system",
        details=f"Loaded {counts['spend_transactions']} spend rows across 3 source systems",
    )
    catalogue.persist()
    catalogue.export_json(PROCESSED_DIR / "governance_catalogue.json")

    spend.to_csv(PROCESSED_DIR / "unified_spend.csv", index=False)

    summary = {
        "row_counts": counts,
        "data_quality": quality,
        "governance": catalogue.coverage_report(expected_assets=len(catalogue.to_frame())),
        "duration_seconds": round(time.time() - started, 2),
    }

    if verbose:
        print("=" * 62)
        print("ProcureSmart AI - ETL PIPELINE RUN")
        print("=" * 62)
        for table, count in counts.items():
            print(f"  loaded {table:<22} {count:>6} rows")
        print("-" * 62)
        print(f"  data completeness      {quality['completeness_pct']}%")
        print(f"  duplicates removed     {quality['duplicates_removed']}")
        print(f"  uncategorised rows     {quality['missing_category']}")
        print(f"  governance assets      {summary['governance']['registered_assets']}")
        print(f"  lineage coverage       {summary['governance']['lineage_coverage_pct']}%")
        print(f"  duration               {summary['duration_seconds']}s")
        print("=" * 62)

    return summary


if __name__ == "__main__":
    run_pipeline()
