from __future__ import annotations

import datetime as dt
from typing import List

import yfinance as yf

from infra.data_store import append_snapshot
from database import db, init_db

sp500_coll = db["sp500_index"]


def fetch_sp500_history(days: int = 30) -> List[dict]:
    """Download S&P 500 index closing prices via Yahoo Finance."""
    init_db()
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
        try:
            dt_obj = (
                dt.datetime.fromisoformat(str(date))
                if not hasattr(date, "date")
                else date
            )
            date_str = str(dt_obj.date())
        except Exception:
            date_str = str(date)
        try:
            close_val = float(val)
        except Exception:
            close_val = float(val.iloc[0]) if hasattr(val, "iloc") else float(val)
        item = {"date": date_str, "close": close_val, "_retrieved": now}
        sp500_coll.update_one({"date": item["date"]}, {"$set": item}, upsert=True)
        records.append(item)
    append_snapshot("sp500_index", records)
    return records


if __name__ == "__main__":
    print(fetch_sp500_history(5)[0])
