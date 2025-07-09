from __future__ import annotations

import datetime as dt
from typing import Iterable, List

import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup, Tag
from typing import cast

from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from config import QUIVER_RATE_SEC
from database import db, pf_coll
from infra.data_store import append_snapshot

analyst_coll = db["analyst_ratings"] if db else pf_coll

rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def _fetch_ticker(sym: str) -> pd.DataFrame:
    url = f"https://finviz.com/quote.ashx?t={sym}&ty=c&p=d&b=1"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="js-table-ratings")
    if not isinstance(table, Tag):
        return pd.DataFrame()
    table = cast(Tag, table)
    rows = []
    now = dt.datetime.now(dt.timezone.utc)
    for row in table.find_all("tr")[1:]:
        if not isinstance(row, Tag):
            continue
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) < 2:
            continue
        item = {
            "ticker": sym,
            "date": cells[0],
            "rating": cells[1].lower(),
            "_retrieved": now,
        }
        rows.append(item)
        analyst_coll.update_one(
            {"ticker": item["ticker"], "date": item["date"], "rating": item["rating"]},
            {"$set": item},
            upsert=True,
        )
    append_snapshot("analyst_ratings", rows)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
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
        info = {}
        try:
            info = yf.Ticker(sym).info
        except Exception:
            info = {}
        rows.append(
            dict(
                symbol=sym,
                upgrades=int(up),
                downgrades=int(down),
                total=int(tot),
                targetMeanPrice=info.get("targetMeanPrice"),
                numAnalystOpinions=info.get("numberOfAnalystOpinions"),
            )
        )
    return pd.DataFrame(rows)
