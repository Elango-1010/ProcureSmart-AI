"""Unit tests: ETL transform layer."""
import pandas as pd
import pytest

from src.etl import transform


class TestNormaliseSupplierName:
    def test_strips_legal_suffix(self):
        assert transform.normalise_supplier_name("Nexa Technologies Pvt Ltd") == "nexa technologies"

    def test_collapses_case_and_punctuation(self):
        a = transform.normalise_supplier_name("NEXA TECHNOLOGIES PVT. LTD.")
        b = transform.normalise_supplier_name("Nexa Technologies")
        assert a == b == "nexa technologies"

    def test_handles_none(self):
        assert transform.normalise_supplier_name(None) == ""

    def test_handles_nan(self):
        assert transform.normalise_supplier_name(float("nan")) == ""


class TestCleanAmounts:
    def test_negative_amounts_become_absolute_and_flagged(self):
        df = pd.DataFrame({"amount": [-100.0, 200.0]})
        out = transform.clean_amounts(df)
        assert list(out["amount"]) == [100.0, 200.0]
        assert list(out["is_credit_note"]) == [True, False]

    def test_non_numeric_rows_dropped(self):
        df = pd.DataFrame({"amount": ["abc", "150"]})
        out = transform.clean_amounts(df)
        assert len(out) == 1
        assert out["amount"].iloc[0] == 150.0


class TestDeduplicate:
    def test_removes_duplicate_transaction_ids(self):
        df = pd.DataFrame({"transaction_id": ["T1", "T1", "T2"], "amount": [10, 10, 20]})
        out = transform.deduplicate(df, key="transaction_id")
        assert len(out) == 2
        assert out.attrs["duplicates_removed"] == 1


class TestStandardiseTextFields:
    def test_trims_and_title_cases(self):
        df = pd.DataFrame({"department": ["  it  "], "category": [" office supplies "]})
        out = transform.standardise_text_fields(df)
        assert out["department"].iloc[0] == "It"
        assert out["category"].iloc[0] == "Office Supplies"

    def test_missing_category_filled(self):
        df = pd.DataFrame({"department": ["IT"], "category": [None]})
        out = transform.standardise_text_fields(df)
        assert out["category"].iloc[0] == "Uncategorised"


class TestValidateSpend:
    def test_reports_completeness_and_schema(self, engine):
        from src.etl.load import read_table
        spend = read_table("spend_transactions", engine)
        report = transform.validate_spend(spend)
        assert report["schema_columns_present"] is True
        assert 0 <= report["completeness_pct"] <= 100
        assert report["total_rows"] == len(spend)
