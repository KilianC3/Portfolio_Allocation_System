import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
import json
from typing import List
import asyncio

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, wiki_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger
import scrapers.universe as univ

log = get_scraper_logger(__name__)
from strategies.wiki_attention import index_map, wiki_title, trending_candidates

wiki_collection = wiki_coll if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_wiki_views(
    page: str = "Apple_Inc",
    days: int = 7,
    ticker: str = "AAPL",
    limit: int | None = None,
) -> List[dict]:
    """Fetch Wikipedia page views via the Wikimedia API.

    Parameters
    ----------
    page : str
        Wikipedia page title using underscores instead of spaces.
    days : int
        Number of days of history to retrieve.
    ticker : str
        Associated ticker symbol used as the primary key in storage.
    """

    log.info(f"fetch_wiki_views start page={page}")
    init_db()

    end = dt.datetime.utcnow().date() - dt.timedelta(days=2)
    start = end - dt.timedelta(days=days - 1)
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/all-agents/{page}/daily/"
        f"{start:%Y%m%d}/{end:%Y%m%d}"
    )
    with scrape_latency.labels("wiki_views").time():
        try:
            async with rate:
                text = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("wiki_views").inc()
            log.exception(f"fetch_wiki_views failed: {exc}")
            raise
    items = json.loads(text).get("items", [])
    now = dt.datetime.now(dt.timezone.utc)
    data: List[dict] = []
    for row in items:
        date = row["timestamp"][:8]
        item = {
            "ticker": ticker,
            "views": row["views"],
            "date": date,
            "_retrieved": now,
        }
        data.append(item)
        wiki_collection.update_one(
            {"ticker": ticker, "date": date},
            {"$set": item},
            upsert=True,
        )
        if limit and len(data) >= limit:
            break
    append_snapshot("wiki_views", data)
    log.info(f"fetched {len(data)} wiki view rows for {page}")
    return data


async def fetch_trending_wiki_views(top_k: int = 10, days: int = 7) -> List[dict]:
    """Collect page views for top trending tickers by z-score.

    Parameters
    ----------
    top_k : int
        Number of tickers to return.
    days : int
        History length for ``fetch_wiki_views``.
    """

    log.info(
        "fetch_trending_wiki_views start top_k=%s days=%s",
        top_k,
        days,
    )
    log.info("trending_candidates start")
    cand_dict = await trending_candidates()
    log.info("trending_candidates end %s candidates", len(cand_dict))
    log.info("index_map start")
    mapping = await asyncio.to_thread(index_map)
    log.info("index_map end")
    allowed = set(mapping.keys())
    cand: List[tuple[str, str]] = [
        (sym, name) for sym, name in cand_dict.items() if sym in allowed
    ]
    seen: set[str] = set()
    pages: List[tuple[str, str]] = []
    for sym, name in cand:
        if sym in seen:
            continue
        log.info("wiki_title start %s", name)
        page = await asyncio.to_thread(wiki_title, name)
        log.info("wiki_title end %s -> %s", name, page)
        if page:
            pages.append((page, sym))
            seen.add(sym)
        if len(pages) >= top_k:
            break

    if len(pages) < top_k:
        for sym, name in mapping.items():
            if sym in seen:
                continue
            page = await asyncio.to_thread(wiki_title, name)
            if page:
                pages.append((page, sym))
                seen.add(sym)
            if len(pages) >= top_k:
                break

    out: List[dict] = []
    for i, (pg, sym) in enumerate(pages[:top_k], 1):
        log.info("fetch_wiki_views progress %s %s/%s", pg, i, min(top_k, len(pages)))
        try:
            out.extend(await fetch_wiki_views(pg, days, ticker=sym))
        except Exception as exc:  # pragma: no cover - network optional
            log.exception(f"fetch_wiki_views failed for %s: %s", pg, exc)
            continue
    log.info("fetched %s trending wiki rows", len(out))
    return out


"""Additional portfolio builder using Wikipedia attention scores.

The functions below replicate the provided `build_portfolio_from_universe.py`
script so the scraper can rank the tracked universe by momentum blended with
Wikipedia `z_score`. Existing async helpers remain untouched for backwards
compatibility and tests.
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import yfinance as yf

from scrapers.yf_utils import extract_close_volume

TOP_N = 25
PRICE_LOOKBACK_SHORT = 5
PRICE_LOOKBACK_LONG = 20
MOM_BLEND_WEIGHTS = (0.6, 0.4)
SCORE_WEIGHTS = dict(momentum=0.7, z=0.3)
PERIOD = "2mo"
TICKER_BATCH = 50
PCT_CLIP = (1, 99)

MAX_TICKERS = 1000
BATCH_SLEEP_SEC = 1.2
BATCH_RETRIES = 2
RETRY_SLEEP_SEC = 2.5

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def robust_minmax(s: pd.Series, pct_clip=PCT_CLIP) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return s
    lo, hi = np.nanpercentile(s, pct_clip[0]), np.nanpercentile(s, pct_clip[1])
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    s = s.clip(lo, hi)
    return (s - lo) / (hi - lo)


def _extract_price_frame(raw: pd.DataFrame | pd.Series | None) -> pd.DataFrame:
    closes, _ = extract_close_volume(raw)
    return closes


def download_batch(batch: list[str]) -> pd.DataFrame:
    attempts = 1 + BATCH_RETRIES
    for attempt in range(1, attempts + 1):
        try:
            raw = yf.download(
                batch,
                period=PERIOD,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            return _extract_price_frame(raw)
        except Exception as exc:  # pragma: no cover - network optional
            print(
                f"[WARN] Batch {batch[:3]}... attempt {attempt}/{attempts} failed: {exc}"
            )
            if attempt < attempts:
                time.sleep(RETRY_SLEEP_SEC)
    return pd.DataFrame()


def get_momentum_returns(tickers: list[str]) -> pd.DataFrame:
    results: dict[str, dict[str, float]] = {}
    clean = [t for t in tickers if isinstance(t, str) and t.strip()]
    total_batches = (len(clean) + TICKER_BATCH - 1) // TICKER_BATCH
    if not clean:
        return pd.DataFrame(columns=["ret_5d", "ret_20d", "momentum"])

    for b_idx in range(0, len(clean), TICKER_BATCH):
        batch = clean[b_idx : b_idx + TICKER_BATCH]
        print(
            f"[INFO] Fetching batch {(b_idx//TICKER_BATCH)+1}/{total_batches} ({len(batch)} tickers) ..."
        )
        px = download_batch(batch)
        if px.empty:
            print("[WARN] Empty price frame for this batch.")
        for t in batch:
            if t not in px.columns:
                continue
            s = px[t].dropna()
            if len(s) < PRICE_LOOKBACK_LONG + 1:
                continue
            last = s.iloc[-1]
            try:
                p5 = s.iloc[-(PRICE_LOOKBACK_SHORT + 1)]
                p20 = s.iloc[-(PRICE_LOOKBACK_LONG + 1)]
            except Exception:
                continue
            if p5 <= 0 or p20 <= 0:
                continue
            ret5 = last / p5 - 1
            ret20 = last / p20 - 1
            mom = MOM_BLEND_WEIGHTS[0] * ret20 + MOM_BLEND_WEIGHTS[1] * ret5
            results[t] = dict(ret_5d=ret5, ret_20d=ret20, momentum=mom)
        time.sleep(BATCH_SLEEP_SEC)

    if not results:
        return pd.DataFrame(columns=["ret_5d", "ret_20d", "momentum"])
    return pd.DataFrame.from_dict(results, orient="index")


def load_universe_from_collection() -> pd.DataFrame | None:
    if db is None:
        return None
    try:
        coll = db["universe"]
        docs = list(coll.find({}))
        if not docs:
            return None
        return pd.DataFrame(docs)
    except Exception as exc:
        print(f"[INFO] universe collection not available: {exc}")
        return None


def load_universe_any() -> pd.DataFrame:
    init_db()
    df = load_universe_from_collection()
    if df is not None:
        print(f"[INFO] Loaded universe from collection: shape={df.shape}")
        return df
    # Fall back to CSV universes when the database is unavailable
    try:
        paths = [
            univ.download_sp500(),
            univ.download_sp400(),
            univ.download_russell2000(),
        ]
        frames = [pd.read_csv(p) for p in paths]
        df = pd.concat(frames, ignore_index=True).drop_duplicates()
        print(f"[INFO] Loaded universe from CSV: shape={df.shape}")
        return df
    except Exception as exc:
        raise RuntimeError("Could not load universe from MariaDB or CSV.") from exc


def build_portfolio(
    universe_df: pd.DataFrame, top_n: int = TOP_N
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker_col = None
    for cand in ("ticker", "symbol", "Symbol", "TICKER", "SYMBOL"):
        if cand in universe_df.columns:
            ticker_col = cand
            break
    if ticker_col is None:
        raise ValueError("Universe DataFrame does not contain a ticker/symbol column.")

    df = universe_df.copy()
    df.rename(columns={ticker_col: "ticker"}, inplace=True)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    if MAX_TICKERS:
        df = df.head(MAX_TICKERS)
        print(f"[INFO] Universe truncated to first {len(df)} tickers (MAX_TICKERS).")

    df = df.drop_duplicates(subset=["ticker"])

    z_col = None
    for cand in ("z_score", "z", "attention_z", "wiki_z"):
        if cand in df.columns:
            z_col = cand
            break
    if z_col is None:
        print("[INFO] No z_score column found; skipping z-score weighting.")
        df["z_score"] = 0.0
    else:
        df["z_score"] = pd.to_numeric(df[z_col], errors="coerce").fillna(0.0)

    mom = get_momentum_returns(df["ticker"].tolist())
    if mom.empty:
        raise RuntimeError("Momentum frame empty – no price data returned.")

    full = df.merge(mom, left_on="ticker", right_index=True, how="inner")
    if full.empty:
        raise RuntimeError("No overlap between universe tickers and momentum data.")

    full["z_norm"] = robust_minmax(full["z_score"])
    full["momentum_norm"] = robust_minmax(full["momentum"])
    full["score"] = (
        SCORE_WEIGHTS["momentum"] * full["momentum_norm"]
        + SCORE_WEIGHTS["z"] * full["z_norm"]
    )

    full = full.sort_values("score", ascending=False).reset_index(drop=True)
    top = full.head(top_n).copy()

    if z_col is None:
        full = full.drop(columns=["z_score", "z_norm"])
        top = top.drop(columns=["z_score", "z_norm"])

    return top, full


def build_universe_portfolio() -> None:
    universe = load_universe_any()
    universe = universe[universe.notna().any(axis=1)]
    if "ticker" not in universe.columns and "symbol" not in universe.columns:
        raise RuntimeError("Universe lacks 'ticker' or 'symbol' column after load.")

    start_time = time.time()
    top, full = build_portfolio(universe, top_n=TOP_N)
    elapsed = time.time() - start_time

    print("\n=== TOP SELECTION ===")
    cols = ["ticker", "ret_5d", "ret_20d", "momentum", "score"]
    if "z_score" in top.columns:
        cols.insert(1, "z_score")
    print(top[cols])

    print("\n=== FULL (head 50) ===")
    print(full.head(50)[cols])

    out_path = os.path.join(REPO_ROOT, "data", "universe_portfolio.csv")
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        full.to_csv(out_path, index=False)
        print(f"\n[INFO] Full scored universe saved to {out_path}")
    except Exception as exc:  # pragma: no cover - filesystem optional
        print(f"[WARN] Could not save output CSV: {exc}")

    print(f"[INFO] Completed in {elapsed:.1f} seconds for {len(full)} tickers.")


if __name__ == "__main__":  # pragma: no cover - manual execution
    build_universe_portfolio()
