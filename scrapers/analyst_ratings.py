from __future__ import annotations

import datetime as dt
from typing import Iterable, List

import pandas as pd

from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from config import QUIVER_RATE_SEC

rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def _fetch_ticker(sym: str) -> pd.DataFrame:
    url = f"https://www.quiverquant.com/sources/analyst/{sym}"
    async with rate:
        html = await scrape_get(url)
    tbls = pd.read_html(html)
    if not tbls:
        return pd.DataFrame()
    df = tbls[0]
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns or "rating" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df["rating"] = df["rating"].str.lower()
    return df


async def fetch_changes(symbols: Iterable[str], weeks: int = 4) -> pd.DataFrame:
    cutoff = pd.Timestamp.today() - pd.Timedelta(weeks=weeks)
    rows: List[dict] = []
    for sym in symbols:
        try:
            df = await _fetch_ticker(sym)
        except Exception:
            continue
        df = df[df["date"] >= cutoff]
        up = df["rating"].str.contains("upgrade").sum()
        down = df["rating"].str.contains("downgrade").sum()
        tot = len(df)
        rows.append(dict(symbol=sym, upgrades=int(up), downgrades=int(down), total=int(tot)))
    return pd.DataFrame(rows)
