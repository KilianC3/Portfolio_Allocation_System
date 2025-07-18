"""ApeWisdom mention data helper.

Fetch ticker mentions from ApeWisdom public API.
"""

from __future__ import annotations

import datetime as dt
from typing import List

import pandas as pd
import requests

from service.logger import get_logger

log = get_logger(__name__)

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


def fetch_page(filter_name: str, page: int) -> dict:
    url = BASE.format(filter=filter_name, page=page)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def get_mentions(filter_name: str = "wallstreetbets", limit: int = 20) -> pd.DataFrame:
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
    return df.sort_values("rank").reset_index(drop=True)


if __name__ == "__main__":
    df = get_mentions("wallstreetbets", 20)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")

