"""Tests: AI intelligence layer.

The maverick detection tests are the closest thing this project has to a
model-accuracy test: generate_data.py deliberately seeds 45 high-value
off-contract transactions, and these tests assert the model actually finds
them - not just that the code runs without crashing.
"""
from src.ai import consolidation, maverick, narrative, savings


class TestMaverickDetection:
    def test_returns_flagged_transactions(self, engine):
        flagged = maverick.detect_maverick_spend(engine=engine)
        assert len(flagged) > 0

    def test_every_flagged_row_has_risk_band(self, engine):
        flagged = maverick.detect_maverick_spend(engine=engine)
        assert set(flagged["risk_band"]) <= {"HIGH", "MEDIUM", "LOW"}

    def test_high_value_off_contract_transactions_are_flagged(self, engine):
        """Recovery test against the seeded maverick pattern."""
        from src.etl.load import read_table
        spend = read_table("spend_transactions", engine)
        seeded_high_value = spend[spend["amount"] > 300_000]
        if len(seeded_high_value) == 0:
            return  # smaller test dataset may not have seeded extreme values

        flagged = maverick.detect_maverick_spend(engine=engine)
        flagged_ids = set(flagged["transaction_id"])
        seeded_ids = set(seeded_high_value["transaction_id"])
        recovered = len(seeded_ids & flagged_ids)
        recall = recovered / max(len(seeded_ids), 1)
        assert recall >= 0.7, f"Only recovered {recall:.0%} of seeded high-value maverick transactions"

    def test_every_flagged_row_has_explanation(self, engine):
        flagged = maverick.detect_maverick_spend(engine=engine)
        assert (flagged["explanation"].str.len() > 0).all()

    def test_validation_metrics_present(self, engine):
        metrics = maverick.model_validation_metrics(engine=engine)
        for key in ("total_transactions", "ml_flagged_count", "flagged_by_both"):
            assert key in metrics

    def test_flag_rate_is_reasonable(self, engine):
        """Sanity bound: flags should be a minority of transactions, not everything."""
        metrics = maverick.model_validation_metrics(engine=engine)
        assert 0 < metrics["ml_flagged_pct"] < 25


class TestConsolidation:
    def test_returns_opportunities_for_multi_supplier_categories(self, engine):
        opportunities = consolidation.consolidation_opportunities(engine=engine)
        assert len(opportunities) > 0
        assert (opportunities["supplier_count"] >= 2).all()

    def test_estimated_savings_non_negative(self, engine):
        opportunities = consolidation.consolidation_opportunities(engine=engine)
        assert (opportunities["estimated_savings"] >= 0).all()

    def test_recommendation_text_present(self, engine):
        opportunities = consolidation.consolidation_opportunities(engine=engine)
        assert (opportunities["recommendation"].str.len() > 20).all()


class TestSavings:
    def test_volume_milestones_only_for_qualifying_suppliers(self, engine):
        milestones = savings.volume_milestone_opportunities(engine=engine)
        if len(milestones) > 0:
            assert (milestones["total_spend"] >= milestones["milestone_reached"]).all()

    def test_renewal_alerts_within_warning_window(self, engine):
        from src.config import CONTRACT_RENEWAL_WARNING_DAYS
        alerts = savings.contract_renewal_alerts(engine=engine)
        if len(alerts) > 0:
            assert (alerts["days_to_expiry"] <= CONTRACT_RENEWAL_WARNING_DAYS).all()

    def test_summary_has_counts(self, engine):
        result = savings.savings_summary(engine=engine)
        assert "renewal_alert_count" in result
        assert "milestone_opportunity_count" in result


class TestNarrative:
    def test_rule_based_fallback_always_works(self, engine):
        """Forces the fallback path so the test never depends on network/API keys."""
        result = narrative.generate_narrative(engine=engine, force_fallback=True)
        assert result["source"] == "rule_based"
        assert len(result["narrative"]) > 50

    def test_narrative_mentions_a_real_figure(self, engine):
        result = narrative.generate_narrative(engine=engine, force_fallback=True)
        assert "%" in result["narrative"] or "Rs" in result["narrative"]
