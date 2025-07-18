from __future__ import annotations

import datetime as dt
from typing import Iterable, List

import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup, Tag
from typing import cast

from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from service.config import QUIVER_RATE_SEC
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

analyst_coll = db["analyst_ratings"] if db else pf_coll

rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
log = get_logger(__name__)


async def _fetch_ticker(sym: str) -> pd.DataFrame:
    log.info(f"_fetch_ticker start sym={sym}")
    init_db()
    url = f"https://finviz.com/quote.ashx?t={sym}&ty=c&p=d&b=1"
    with scrape_latency.labels("analyst_ratings").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("analyst_ratings").inc()
            log.warning(f"_fetch_ticker failed for {sym}: {exc}")
            raise
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
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    df = df.dropna(subset=["date"])
    log.info(f"fetched {len(df)} analyst rows for {sym}")
    return df


async def fetch_analyst_ratings(symbols: Iterable[str]) -> List[dict]:
    """Fetch analyst rating tables for a list of tickers."""
    log.info("fetch_analyst_ratings start")
    all_rows: List[dict] = []
    for sym in symbols:
        try:
            df = await _fetch_ticker(sym)
        except Exception:
            continue
        all_rows.extend(df.to_dict("records"))
    log.info(f"fetched {len(all_rows)} analyst rating rows")
    return all_rows


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
