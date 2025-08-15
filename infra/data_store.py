"""Simple columnar data store for scraped data."""

from __future__ import annotations

import datetime as dt
from typing import List, Dict

import pandas as pd

import time

from database import db
from infra.github_backup import backup_records
from service.logger import get_logger


_log = get_logger("data_store")


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
            elif pd.isna(val):
                item[col] = None
        data.append(item)
    if db.conn:
        coll = db[table]
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                coll.insert_many(data)
                break
            except Exception as exc:
                _log.error(
                    "snapshot insert failed",
                    table=table,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < attempts:
                    time.sleep(2 ** (attempt - 1))
    backup_records(table, data)


def has_recent_rows(table: str, since: dt.datetime) -> bool:
    """Return True if ``table`` contains recent rows in MariaDB."""
    if not db.conn:
        return False
    coll = db[table]
    return coll.count_documents({"_retrieved": {"$gte": since}}) > 0
