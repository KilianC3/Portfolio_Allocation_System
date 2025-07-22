"""Simple columnar data store for scraped data."""

from __future__ import annotations

import datetime as dt
from typing import List, Dict

import pandas as pd

from database import db


def append_snapshot(table: str, records: List[Dict]) -> None:
    """Insert ``records`` into the Postgres table if a connection is available."""
    if not records or not db.conn:
        return
    coll = db[table]
    data = []
    for row in records:
        item = row.copy()
        for col, val in item.items():
            if isinstance(val, dt.datetime):
                item[col] = val.replace(tzinfo=None)
        data.append(item)
    try:
        coll.insert_many(data)
    except Exception:
        pass


def has_recent_rows(table: str, since: dt.datetime) -> bool:
    """Return True if ``table`` contains recent rows in Postgres."""
    if not db.conn:
        return False
    coll = db[table]
    return coll.count_documents({"_retrieved": {"$gte": since}}) > 0
