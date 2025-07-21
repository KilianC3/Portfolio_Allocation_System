from __future__ import annotations

import datetime as dt
from typing import List

import yfinance as yf

from infra.data_store import append_snapshot
from database import db, init_db
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger

log = get_scraper_logger(__name__)

sp500_coll = db["sp500_index"]


def fetch_sp500_history(days: int = 30) -> List[dict]:
    """Download S&P 500 index closing prices via Yahoo Finance."""
    log.info("fetch_sp500_history start")
    init_db()
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    with scrape_latency.labels("sp500_index").time():
        try:
            df = yf.download(
                "^GSPC", start=start, end=end, interval="1d", progress=False
            )["Close"]
        except Exception as exc:
            scrape_errors.labels("sp500_index").inc()
            log.warning(f"fetch_sp500_history failed: {exc}")
            raise
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
    log.info(f"fetched {len(records)} sp500 rows")
    return records


if __name__ == "__main__":
    import pandas as pd

    rows = fetch_sp500_history(5)
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
