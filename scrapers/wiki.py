import datetime as dt
import json
from typing import List

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, wiki_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger

log = get_scraper_logger(__name__)
from strategies.wiki_attention import index_map, wiki_title

wiki_collection = wiki_coll if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_wiki_views(page: str = "Apple_Inc", days: int = 7) -> List[dict]:
    """Fetch Wikipedia page views via the Wikimedia API."""

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
            log.warning(f"fetch_wiki_views failed: {exc}")
            raise
    items = json.loads(text).get("items", [])
    now = dt.datetime.now(dt.timezone.utc)
    data: List[dict] = []
    for row in items:
        date = row["timestamp"][:8]
        item = {
            "page": page,
            "views": row["views"],
            "date": date,
            "_retrieved": now,
        }
        data.append(item)
        wiki_collection.update_one(
            {"page": page, "date": date},
            {"$set": item},
            upsert=True,
        )
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
    mapping = index_map()
    universe = load_universe_any()
    top_df, _ = build_portfolio(universe, top_n=top_k)
    pages = []
    for sym in top_df["ticker"]:
        name = mapping.get(sym, sym)
        page = wiki_title(name)
        if page:
            pages.append(page)

    top = pages[:top_k]
    out: List[dict] = []
    for pg in top:
        try:
            out.extend(await fetch_wiki_views(pg, days))
        except Exception as exc:  # pragma: no cover - network optional
            log.warning(f"fetch_wiki_views failed for {pg}: {exc}")
            continue
    log.info(f"fetched {len(out)} trending wiki rows")
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
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw, pd.DataFrame):
        if isinstance(raw.columns, pd.MultiIndex):
            lvl0 = raw.columns.get_level_values(0)
            for cand in ("Adj Close", "Close"):
                if cand in lvl0:
                    return raw.xs(cand, axis=1)
            return raw.xs(lvl0[0], axis=1)
        return raw
    if isinstance(raw, pd.Series):
        return raw.to_frame()
    return pd.DataFrame()


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


def load_universe_from_duckdb() -> pd.DataFrame | None:
    duck_path = os.path.join(REPO_ROOT, "data", "altdata.duckdb")
    if not os.path.exists(duck_path):
        return None
    try:
        import duckdb

        con = duckdb.connect(duck_path, read_only=True)
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        matches = [t for t in tables if t.lower() == "universe"]
        if not matches:
            return None
        tbl = matches[0]
        return con.execute(f"SELECT * FROM {tbl}").fetchdf()
    except Exception as exc:
        print(f"[INFO] DuckDB universe load failed: {exc}")
        return None


def load_universe_any() -> pd.DataFrame:
    init_db()
    df = load_universe_from_collection()
    if df is not None:
        print(f"[INFO] Loaded universe from collection: shape={df.shape}")
        return df
    df = load_universe_from_duckdb()
    if df is not None:
        print(f"[INFO] Loaded universe from DuckDB: shape={df.shape}")
        return df
    raise RuntimeError("Could not load universe from any source.")


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
        rng = np.random.default_rng(seed=42)
        df["z_score"] = rng.normal(0, 1, len(df)) + 1.0
        print("[INFO] No z_score column found; fabricated placeholder scores.")
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
    print(top[["ticker", "z_score", "ret_5d", "ret_20d", "momentum", "score"]])

    print("\n=== FULL (head 50) ===")
    print(
        full.head(50)[["ticker", "z_score", "ret_5d", "ret_20d", "momentum", "score"]]
    )

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
