from __future__ import annotations

import asyncio
import datetime as dt
from typing import List

import pandas as pd

from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger
from .apewisdom_api import get_mentions as aw_get_mentions

log = get_logger(__name__)


def run_analysis(days: int, top_n: int) -> pd.DataFrame:
    """Return top WallStreetBets tickers from ApeWisdom."""
    df = aw_get_mentions("wallstreetbets", top_n)
    if df.empty:
        return df
    if "ticker" in df.columns and "symbol" not in df.columns:
        df = df.rename(columns={"ticker": "symbol"})
    order = [
        c
        for c in [
            "symbol",
            "mentions",
            "upvotes",
            "rank",
            "rank_24h_ago",
            "mentions_24h_ago",
            "retrieved_utc",
        ]
        if c in df.columns
    ]
    return df[order].head(top_n)


reddit_coll = db["reddit_mentions"] if db else pf_coll


async def fetch_wsb_mentions(days: int = 7, top_n: int = 15) -> List[dict]:
    """Collect WallStreetBets mention counts via ApeWisdom.

    The ``days`` parameter is ignored and remains for backwards compatibility.
    """
    log.info("fetch_wsb_mentions start")
    init_db()
    with scrape_latency.labels("reddit_mentions").time():
        try:
            df = await asyncio.to_thread(aw_get_mentions, "wallstreetbets", top_n)
        except Exception as exc:
            scrape_errors.labels("reddit_mentions").inc()
            log.warning(f"fetch_wsb_mentions failed: {exc}")
            raise
    if df.empty:
        return []
    now = dt.datetime.now(dt.timezone.utc)
    rows: List[dict] = []
    for _, row in df.iterrows():
        item = {
            "ticker": row.get("ticker") or row.get("symbol"),
            "mentions": int(row.get("mentions", 0)),
            "pos": None,
            "neu": None,
            "neg": None,
            "date": str(dt.date.today()),
            "_retrieved": now,
        }
        reddit_coll.update_one(
            {"ticker": item["ticker"], "date": item["date"]},
            {"$set": item},
            upsert=True,
        )
        rows.append(item)
    append_snapshot("reddit_mentions", rows)
    log.info(f"fetched {len(rows)} wsb rows")
    return rows


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_wsb_mentions(1, 2))
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
