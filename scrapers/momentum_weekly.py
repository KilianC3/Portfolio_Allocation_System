from __future__ import annotations

"""Weekly momentum scrapers.

Each helper fetches weekly price data in batches and stores only the
selected tickers for each strategy.
"""

import math
import sys
import datetime as dt
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import yfinance as yf

from service.logger import get_scraper_logger
from database import (
    init_db,
    vol_mom_coll,
    lev_sector_coll,
    sector_mom_coll,
    smallcap_mom_coll,
    upgrade_mom_coll,
)
from scrapers.analyst_ratings import fetch_changes
from scrapers.wiki import load_universe_any
from strategies.leveraged_sector import DEFAULT_TICKERS as LEVERAGED
from strategies.sector_momentum import SECTOR_ETFS
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


log = get_scraper_logger(__name__)

_CHUNK = 100
_VOL_N = 5
_LEV_N = 3
_SECTOR_N = 3
_SMALL_N = 10
_UPGRADE_N = 15


def _weekly_closes(tickers: list[str], weeks: int) -> pd.DataFrame:
    """Return weekly close prices for ``tickers``."""
    df = yf.download(
        tickers,
        period=f"{weeks + 1}wk",
        interval="1wk",
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs("Close", level=0, axis=1)
    return df.dropna(how="all")


def _score_vol_mom(px: pd.DataFrame) -> pd.DataFrame:
    pct = px.pct_change()
    ret_52w = px.iloc[-1] / px.iloc[0] - 1
    vol_12w = pct.tail(12).std() * math.sqrt(52)
    score = ret_52w / vol_12w.replace(0, math.nan)
    df = pd.DataFrame({"score": score, "ret_52w": ret_52w, "vol_12w": vol_12w})
    return df.dropna()


def fetch_volatility_momentum_summary(weeks: int = 52) -> List[dict]:
    """Store volatility-scaled momentum scores for the full universe."""
    tickers = load_universe_any()
    init_db()
    score_frames: list[pd.DataFrame] = []
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("volatility_momentum").time():
        for i in range(0, len(tickers), _CHUNK):
            batch = tickers[i : i + _CHUNK]
            try:
                px = _weekly_closes(batch, weeks)
            except Exception as exc:  # pragma: no cover - network optional
                scrape_errors.labels("volatility_momentum").inc()
                log.exception("vol batch %s failed: %s", batch[:3], exc)
                continue
            df = _score_vol_mom(px)
            score_frames.append(df)
    if not score_frames:
        return []

    all_scores = pd.concat(score_frames)
    top = all_scores.sort_values("score", ascending=False).head(_VOL_N)
    vol_mom_coll.delete_many({"date": end})
    rows: List[dict] = []
    for sym in top.index:
        item = {
            "symbol": sym,
            "date": end,
            "_retrieved": now,
        }
        vol_mom_coll.update_one(
            {"symbol": sym, "date": end}, {"$set": item}, upsert=True
        )
        rows.append(item)
    if rows:
        append_snapshot("volatility_momentum", rows)
    log.info("volatility_momentum wrote %d rows", len(rows))
    return rows


def fetch_leveraged_sector_summary(weeks: int = 13) -> List[dict]:
    """Store 13-week returns for leveraged sector ETFs."""
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("leveraged_sector_momentum").time():
        try:
            px = _weekly_closes(list(LEVERAGED), weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("leveraged_sector_momentum").inc()
            log.exception("leveraged batch failed: %s", exc)
            return []
        ret = px.iloc[-1] / px.iloc[-weeks] - 1
        top = ret.sort_values(ascending=False).head(_LEV_N)
        rows = []
        lev_sector_coll.delete_many({"date": end})
        for sym in top.index:
            item = {
                "symbol": sym,
                "date": end,
                "_retrieved": now,
            }
            lev_sector_coll.update_one(
                {"symbol": sym, "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("leveraged_sector_momentum", rows)
    log.info("leveraged_sector_momentum wrote %d rows", len(rows))
    return rows


def fetch_sector_momentum_summary(weeks: int = 26) -> List[dict]:
    """Store 26-week returns for S&P sector ETFs."""
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("sector_momentum_weekly").time():
        try:
            px = _weekly_closes(list(SECTOR_ETFS), weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("sector_momentum_weekly").inc()
            log.exception("sector batch failed: %s", exc)
            return []
        ret = px.iloc[-1] / px.iloc[-weeks] - 1
        top = ret.sort_values(ascending=False).head(_SECTOR_N)
        rows = []
        sector_mom_coll.delete_many({"date": end})
        for sym in top.index:
            item = {
                "symbol": sym,
                "date": end,
                "_retrieved": now,
            }
            sector_mom_coll.update_one(
                {"symbol": sym, "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("sector_momentum_weekly", rows)
    log.info("sector_momentum_weekly wrote %d rows", len(rows))
    return rows


def fetch_smallcap_momentum_summary(
    tickers: Iterable[str], weeks: int = 4
) -> List[dict]:
    """Store top weekly return small caps instead of full universe."""
    symbols = list(tickers)
    if not symbols:
        return []
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    rets: list[pd.DataFrame] = []
    with scrape_latency.labels("smallcap_momentum_weekly").time():
        for i in range(0, len(symbols), _CHUNK):
            batch = symbols[i : i + _CHUNK]
            try:
                px = _weekly_closes(batch, weeks)
            except Exception as exc:  # pragma: no cover - network optional
                scrape_errors.labels("smallcap_momentum_weekly").inc()
                log.exception("smallcap batch %s failed: %s", batch[:3], exc)
                continue
            last = px.iloc[-1]
            ret = px.iloc[-1] / px.iloc[-weeks] - 1
            df = pd.DataFrame({"price": last, "ret": ret})
            rets.append(df)
    if not rets:
        return []

    all_df = pd.concat(rets)
    top = (
        all_df.dropna(subset=["ret"]).sort_values("ret", ascending=False).head(_SMALL_N)
    )
    smallcap_mom_coll.delete_many({"date": end})
    rows: List[dict] = []
    for sym in top.index:
        item = {
            "symbol": sym,
            "date": end,
            "_retrieved": now,
        }
        smallcap_mom_coll.update_one(
            {"symbol": sym, "date": end}, {"$set": item}, upsert=True
        )
        rows.append(item)
    if rows:
        append_snapshot("smallcap_momentum_weekly", rows)
    log.info("smallcap_momentum_weekly wrote %d rows", len(rows))
    return rows


async def fetch_upgrade_momentum_summary(
    universe: Iterable[str], weeks: int = 4
) -> List[dict]:
    """Store analyst upgrade momentum ratios for ``universe``."""
    symbols = list(universe)
    if not symbols:
        return []
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("upgrade_momentum_weekly").time():
        try:
            df = await fetch_changes(symbols, weeks=weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("upgrade_momentum_weekly").inc()
            log.exception("upgrade fetch failed: %s", exc)
            return []
        df["ratio"] = (df["upgrades"] - df["downgrades"]) / df["total"].replace(
            0, math.nan
        )
        df = df.dropna(subset=["ratio"]).sort_values("ratio", ascending=False)
        top = df.head(_UPGRADE_N)
        rows: List[dict] = []
        upgrade_mom_coll.delete_many({"date": end})
        for _, row in top.iterrows():
            item = {
                "symbol": row["symbol"],
                "date": end,
                "_retrieved": now,
            }
            upgrade_mom_coll.update_one(
                {"symbol": item["symbol"], "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("upgrade_momentum_weekly", rows)
    log.info("upgrade_momentum_weekly wrote %d rows", len(rows))
    return rows
