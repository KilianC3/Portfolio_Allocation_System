"""Simple columnar data store for scraped data."""

from __future__ import annotations

import datetime as dt
from typing import List, Dict

import pandas as pd

from database import db
from infra.github_backup import backup_records


def append_snapshot(table: str, records: List[Dict]) -> None:
    """Insert ``records`` into the MariaDB table and GitHub backup."""
    if not records:
        return
    data = []
    for row in records:
        item = row.copy()
        for col, val in item.items():
            if isinstance(val, dt.datetime):
                item[col] = val.replace(tzinfo=None)
        data.append(item)
    if db.conn:
        coll = db[table]
        try:
            coll.insert_many(data)
        except Exception:
            pass
    backup_records(table, data)


def has_recent_rows(table: str, since: dt.datetime) -> bool:
    """Return True if ``table`` contains recent rows in MariaDB."""
    if not db.conn:
        return False
    coll = db[table]
    return coll.count_documents({"_retrieved": {"$gte": since}}) > 0
