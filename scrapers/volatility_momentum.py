from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
def _tickers_from_universe(df: pd.DataFrame) -> List[str]:
    """Extract a list of ticker symbols from ``df``."""
    ticker_col = None
    for cand in ("ticker", "symbol", "Symbol", "TICKER", "SYMBOL"):
        if cand in df.columns:
            ticker_col = cand
            break
    if ticker_col is None:
        raise ValueError("Universe DataFrame does not contain a ticker column")
    return df[ticker_col].astype(str).str.upper().str.strip().tolist()


def fetch_volatility_momentum_summary(
    weeks: int = 52,
    top_n: int = _VOL_N,
    max_tickers: int | None = None,
) -> List[dict]:
    """Store volatility-scaled momentum scores for the full universe."""
    log.info(
        "fetch_volatility_momentum_summary start weeks=%d top_n=%d max_tickers=%s",
        weeks,
        top_n,
        max_tickers,
    )
    universe_df = load_universe_any()
    tickers = _tickers_from_universe(universe_df)
    if max_tickers is not None:
        tickers = tickers[:max_tickers]
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
            if len(px) < weeks + 1:
                log.warning("vol batch %s insufficient rows (%d)", batch[:3], len(px))
                continue
            df = _score_vol_mom(px)
            score_frames.append(df)
    if not score_frames:
        return []
    all_scores = pd.concat(score_frames)
    top = all_scores.sort_values("score", ascending=False).head(top_n)
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


if __name__ == "__main__":
    rows = fetch_volatility_momentum_summary(top_n=5, max_tickers=50)
    print(f"ROWS={len(rows)}")
