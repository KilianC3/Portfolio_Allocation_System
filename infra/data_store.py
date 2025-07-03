"""Simple columnar data store for scraped data."""
from __future__ import annotations

import os
from typing import List, Dict

import pandas as pd
import duckdb

DB_PATH = os.getenv("DATA_DB_PATH", "data/altdata.duckdb")


def append_snapshot(table: str, records: List[Dict]) -> None:
    """Append records to the DuckDB table creating it if necessary."""
    if not records:
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)
    df = pd.DataFrame(records)
    con.register("_tmp", df)
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM _tmp LIMIT 0")
    con.execute(f"INSERT INTO {table} SELECT * FROM _tmp")
    con.unregister("_tmp")
    con.close()
