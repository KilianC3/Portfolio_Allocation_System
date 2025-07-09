from __future__ import annotations

import datetime as dt
from typing import List

import yfinance as yf

from infra.data_store import append_snapshot
from database import db

sp500_coll = db["sp500_index"]


def fetch_sp500_history(days: int = 30) -> List[dict]:
    """Download S&P 500 index closing prices via Yahoo Finance."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    df = yf.download("^GSPC", start=start, end=end, interval="1d", progress=False)[
        "Close"
    ]
    if df.empty:
        return []
    now = dt.datetime.now(dt.timezone.utc)
    records = []
    for date, val in df.items():
        item = {"date": str(date.date()), "close": float(val), "_retrieved": now}
        sp500_coll.update_one({"date": item["date"]}, {"$set": item}, upsert=True)
        records.append(item)
    append_snapshot("sp500_index", records)
    return records


if __name__ == "__main__":
    print(fetch_sp500_history(5)[0])
