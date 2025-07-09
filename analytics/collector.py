"""Daily analytics snapshot collector."""

import os
import duckdb
import pandas as pd

DB_PATH = os.getenv("ANALYTICS_DB", "analytics.duckdb")


def record_snapshot(portfolio_id: str, data: pd.DataFrame) -> None:
    """Append daily snapshot rows to DuckDB."""
    con = duckdb.connect(DB_PATH)
    data = data.copy()
    data.insert(0, "portfolio_id", portfolio_id)
    con.register("_data", data)
    con.execute("CREATE TABLE IF NOT EXISTS snapshots AS SELECT * FROM _data LIMIT 0")
    con.execute("INSERT INTO snapshots SELECT * FROM _data")
    con.unregister("_data")
    con.close()
