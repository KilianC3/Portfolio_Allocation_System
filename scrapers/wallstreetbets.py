from __future__ import annotations

import asyncio
import datetime as dt
from typing import List

import pandas as pd

from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from scripts.wsb_strategy import run_analysis

reddit_coll = db["reddit_mentions"] if db else pf_coll


async def fetch_wsb_mentions(days: int = 7, top_n: int = 15) -> List[dict]:
    """Collect WallStreetBets mention counts."""
    init_db()
    df = await asyncio.to_thread(run_analysis, days, top_n)
    if df.empty:
        return []
    now = dt.datetime.now(dt.timezone.utc)
    rows: List[dict] = []
    for _, row in df.iterrows():
        item = {
            "ticker": row["symbol"],
            "mentions": int(row["mentions"]),
            "pos": int(row.get("pos", 0)),
            "neu": int(row.get("neu", 0)),
            "neg": int(row.get("neg", 0)),
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
    return rows


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(fetch_wsb_mentions(1, 2)))
