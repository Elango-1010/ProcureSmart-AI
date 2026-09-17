"""Load stage - writes conformed frames into the procurement database."""
from __future__ import annotations

import pandas as pd

from ..schema import get_engine, init_db


def load_frame(df: pd.DataFrame, table: str, engine=None, if_exists: str = "replace") -> int:
    """Write a DataFrame to a table and return the row count written."""
    engine = engine or get_engine()
    init_db(engine)
    df.to_sql(table, engine, if_exists=if_exists, index=False)
    return len(df)


def read_table(table: str, engine=None) -> pd.DataFrame:
    """Read a whole table back out - used by analytics and tests."""
    engine = engine or get_engine()
    return pd.read_sql_table(table, engine)


def query(sql: str, engine=None) -> pd.DataFrame:
    engine = engine or get_engine()
    return pd.read_sql_query(sql, engine)
