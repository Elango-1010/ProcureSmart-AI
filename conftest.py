"""Shared fixtures - builds a fresh in-memory-backed test database once per session
using the real synthetic data generator and real ETL pipeline, so every test
exercises actual code paths rather than mocked data.
"""
import pytest
from sqlalchemy import create_engine

from src import generate_data
from src.etl import pipeline as etl_pipeline
from src.schema import init_db


@pytest.fixture(scope="session")
def test_engine(tmp_path_factory):
    """A SQLite file DB (shared engine, not :memory:, so multiple connections work),
    populated by actually running generate_data + the real ETL pipeline.
    """
    db_path = tmp_path_factory.mktemp("db") / "test_procuresmart.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    init_db(engine)

    generate_data.generate_all(n_spend=1200)  # smaller volume keeps the suite fast
    etl_pipeline.run_pipeline(engine=engine, verbose=False)

    return engine


@pytest.fixture()
def engine(test_engine):
    return test_engine
