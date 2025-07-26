from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
from typing import List

import yfinance as yf

from infra.data_store import append_snapshot
from database import db, init_db
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger

log = get_scraper_logger(__name__)

sp500_coll = db["sp500_index"]


def fetch_sp500_history(days: int = 365) -> List[dict]:
    """Download S&P 500 weekly OHLCV via Yahoo Finance."""
    log.info("fetch_sp500_history start")
    init_db()
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    with scrape_latency.labels("sp500_index").time():
        try:
            df = yf.download(
                "^GSPC",
                start=start,
                end=end,
                interval="1wk",
                progress=False,
            )
        except Exception as exc:
            scrape_errors.labels("sp500_index").inc()
            log.exception(f"fetch_sp500_history failed: {exc}")
            raise
    if df.empty:
        return []
    now = dt.datetime.now(dt.timezone.utc)
    records = []
    for date, row in df.iterrows():
        try:
            date_obj = (
                date if hasattr(date, "date") else dt.datetime.fromisoformat(str(date))
            )
            date_str = str(date_obj.date())
        except Exception:
            date_str = str(date)
        item = {
            "date": date_str,
            "open": float(row.get("Open", 0)),
            "high": float(row.get("High", 0)),
            "low": float(row.get("Low", 0)),
            "close": float(row.get("Close", row[0] if len(row) else 0)),
            "volume": int(row.get("Volume", 0)),
            "_retrieved": now,
        }
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
