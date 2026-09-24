"""Tests: spend, supplier and budget analytics."""
from src.analytics import budget, spend, supplier


class TestSpendAnalytics:
    def test_total_spend_positive(self, engine):
        assert spend.total_spend(engine=engine) > 0

    def test_by_department_sums_to_total(self, engine):
        by_dept = spend.spend_by_department(engine=engine)
        total = spend.total_spend(engine=engine)
        assert abs(by_dept["total_spend"].sum() - total) < 1.0

    def test_by_category_percentages_sum_to_100(self, engine):
        by_cat = spend.spend_by_category(engine=engine)
        assert abs(by_cat["pct_of_total"].sum() - 100.0) < 0.5

    def test_contract_status_breakdown_covers_all_spend(self, engine):
        breakdown = spend.contract_status_breakdown(engine=engine)
        total = spend.total_spend(engine=engine)
        assert abs(breakdown["total_spend"].sum() - total) < 1.0

    def test_off_contract_pct_in_valid_range(self, engine):
        pct = spend.off_contract_spend_pct(engine=engine)
        assert 0 <= pct <= 100

    def test_spend_summary_has_all_keys(self, engine):
        summary = spend.spend_summary(engine=engine)
        for key in ("total_spend", "by_department", "by_category", "top_suppliers",
                    "monthly_trend", "off_contract_spend_pct"):
            assert key in summary


class TestSupplierAnalytics:
    def test_duplicate_suppliers_detected(self, engine):
        """The two duplicate-name groups planted in generate_data.py must be caught."""
        from src.etl.load import read_table
        suppliers = read_table("suppliers", engine)
        dupes = supplier.detect_duplicate_suppliers(suppliers)
        assert len(dupes) >= 2
        canonical_names = set(dupes["canonical_name"])
        assert "nexa technologies" in canonical_names
        assert "orion office supplies" in canonical_names

    def test_concentration_within_bounds(self, engine):
        from src.etl.load import read_table
        spend_df = read_table("spend_transactions", engine)
        result = supplier.supplier_concentration(spend_df, top_n=5)
        assert 0 <= result.iloc[0]["concentration_pct"] <= 100

    def test_contract_compliance_within_bounds(self, engine):
        from src.etl.load import read_table
        spend_df = read_table("spend_transactions", engine)
        compliance = supplier.contract_compliance(spend_df)
        assert (compliance["compliance_pct"] >= 0).all()
        assert (compliance["compliance_pct"] <= 100).all()


class TestBudgetAnalytics:
    def test_utilisation_has_all_departments(self, engine):
        from src.config import DEPARTMENTS
        util = budget.budget_utilisation(engine=engine)
        assert set(util["department"]) == set(DEPARTMENTS)

    def test_kpis_present(self, engine):
        kpis = budget.procurement_kpis(engine=engine)
        for key in ("total_spend", "off_contract_spend_pct",
                    "requisition_approval_rate_pct", "pending_requisitions"):
            assert key in kpis

    def test_approval_rate_in_valid_range(self, engine):
        kpis = budget.procurement_kpis(engine=engine)
        assert 0 <= kpis["requisition_approval_rate_pct"] <= 100
