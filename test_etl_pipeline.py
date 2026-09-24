"""Integration tests: full ETL pipeline, database load, and governance catalogue."""
from src.etl.load import read_table


class TestPipelineLoadsAllDomains:
    def test_spend_transactions_loaded(self, engine):
        df = read_table("spend_transactions", engine)
        assert len(df) > 0

    def test_suppliers_loaded(self, engine):
        df = read_table("suppliers", engine)
        assert len(df) > 0

    def test_contracts_loaded(self, engine):
        df = read_table("contracts", engine)
        assert len(df) > 0

    def test_requisitions_loaded(self, engine):
        df = read_table("requisitions", engine)
        assert len(df) > 0

    def test_three_procurement_domains_present(self, engine):
        """RFP minimum coverage: at least 3 procurement data domains managed."""
        domains = ["spend_transactions", "requisitions", "contracts"]
        for table in domains:
            assert len(read_table(table, engine)) > 0


class TestUnifiedSchema:
    def test_spend_has_required_columns(self, engine):
        from src.schema import UNIFIED_SPEND_COLUMNS
        df = read_table("spend_transactions", engine)
        for col in UNIFIED_SPEND_COLUMNS:
            assert col in df.columns

    def test_contract_status_values_are_valid(self, engine):
        df = read_table("spend_transactions", engine)
        assert set(df["contract_status"].unique()) <= {
            "ON_CONTRACT", "OFF_CONTRACT", "NO_CONTRACT"
        }

    def test_no_duplicate_transaction_ids(self, engine):
        df = read_table("spend_transactions", engine)
        assert df["transaction_id"].duplicated().sum() == 0


class TestGovernanceCatalogue:
    def test_assets_registered(self, engine):
        df = read_table("data_assets", engine)
        assert len(df) > 0

    def test_every_source_file_registered(self, engine):
        from src.etl.extract import list_source_files
        assets = read_table("data_assets", engine)
        source_files = list_source_files()
        for f in source_files:
            assert (assets["asset_name"] == f).any(), f"{f} not in catalogue"

    def test_derived_tables_have_lineage(self, engine):
        assets = read_table("data_assets", engine)
        tables = assets[assets["asset_type"].isin(["TABLE", "DERIVED_VIEW"])]
        assert (tables["upstream_assets"].str.len() > 0).all()

    def test_audit_log_recorded_pipeline_run(self, engine):
        audit = read_table("audit_log", engine)
        assert (audit["action"] == "EXECUTED").any()
