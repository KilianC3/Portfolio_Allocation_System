"""Daily analytics snapshot collector."""

import pandas as pd

from database import db


def record_snapshot(portfolio_id: str, data: pd.DataFrame) -> None:
    """Append daily snapshot rows to Postgres."""
    if not db.conn:
        return
    coll = db["snapshots"]
    df = data.copy()
    df.insert(0, "portfolio_id", portfolio_id)
    coll.insert_many(df.to_dict(orient="records"))
