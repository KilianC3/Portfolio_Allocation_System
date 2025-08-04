from __future__ import annotations

import math
import datetime as dt
from typing import List

import pandas as pd

from service.logger import get_scraper_logger
from database import init_db, vol_mom_coll
from .momentum_common import _CHUNK, _weekly_closes
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from scrapers.wiki import load_universe_any

log = get_scraper_logger(__name__)
_VOL_N = 5


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
        item = {"symbol": sym, "date": end, "_retrieved": now}
        vol_mom_coll.update_one(
            {"symbol": sym, "date": end}, {"$set": item}, upsert=True
        )
        rows.append(item)
    if rows:
        append_snapshot("volatility_momentum", rows)
    log.info("volatility_momentum wrote %d rows", len(rows))
    return rows
