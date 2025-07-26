from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import datetime as dt
from typing import List

import pandas as pd
import requests

from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger

BASE = "https://apewisdom.io/api/v1.0/filter/{filter}/page/{page}"
FILTERS = {
    "all",
    "all-stocks",
    "all-crypto",
    "4chan",
    "CryptoCurrency",
    "CryptoCurrencies",
    "Bitcoin",
    "SatoshiStreetBets",
    "CryptoMoonShots",
    "CryptoMarkets",
    "stocks",
    "wallstreetbets",
    "options",
    "WallStreetbetsELITE",
    "Wallstreetbetsnew",
    "SPACs",
    "investing",
    "Daytrading",
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

log = get_scraper_logger(__name__)


def fetch_page(filter_name: str, page: int) -> dict:
    """Return raw page JSON from ApeWisdom."""
    url = BASE.format(filter=filter_name, page=page)
    log.info(f"fetch_page start filter={filter_name} page={page}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - network optional
        log.exception(f"fetch_page failed: {exc}")
        raise
    return r.json()


def get_mentions(filter_name: str = "wallstreetbets", limit: int = 20) -> pd.DataFrame:
    """Return ``limit`` most mentioned tickers for ``filter_name``."""
    log.info(f"get_mentions start filter={filter_name} limit={limit}")
    if filter_name not in FILTERS:
        raise ValueError(f"Unsupported filter '{filter_name}'")
    if limit <= 0:
        raise ValueError("limit must be > 0")

    rows: List[dict] = []
    page = 1
    while len(rows) < limit:
        data = fetch_page(filter_name, page)
        for rec in data.get("results", []):
            rows.append(rec)
            if len(rows) >= limit:
                break
        if page >= data.get("pages", 0):
            break
        page += 1

    df = pd.DataFrame(rows[:limit])
    int_cols = ["rank", "mentions", "upvotes", "rank_24h_ago", "mentions_24h_ago"]
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df["retrieved_utc"] = dt.datetime.now(dt.timezone.utc)
    order = [
        c
        for c in [
            "rank",
            "ticker",
            "name",
            "mentions",
            "upvotes",
            "rank_24h_ago",
            "mentions_24h_ago",
            "retrieved_utc",
        ]
        if c in df.columns
    ]
    df = df[order]
    out = df.sort_values("rank").reset_index(drop=True)
    log.info(f"get_mentions fetched {len(out)} rows")
    return out


def run_analysis(days: int, top_n: int) -> pd.DataFrame:
    """Return top WallStreetBets tickers from ApeWisdom."""
    df = get_mentions("wallstreetbets", top_n)
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


async def fetch_wsb_mentions(days: int = 7, top_n: int = 20) -> List[dict]:
    """Collect WallStreetBets mention counts via ApeWisdom.

    The ``days`` parameter is ignored and remains for backwards compatibility.
    """
    log.info("fetch_wsb_mentions start")
    init_db()
    with scrape_latency.labels("reddit_mentions").time():
        try:
            df = await asyncio.to_thread(get_mentions, "wallstreetbets", top_n)
        except Exception as exc:
            scrape_errors.labels("reddit_mentions").inc()
            log.exception(f"fetch_wsb_mentions failed: {exc}")
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
