from __future__ import annotations

import datetime as dt
import functools
import logging
import math
import re
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import requests  # type: ignore[import-untyped]
from io import StringIO
import wikipedia
import yfinance as yf
from tqdm import tqdm
from scrapers.yf_utils import extract_close_volume
from unidecode import unidecode

from scrapers.universe import load_sp500, load_sp400

_log = logging.getLogger("scrapers.wiki_attention")
_log.setLevel(logging.INFO)

REST = "https://wikimedia.org/api/rest_v1"
HEADERS = {"User-Agent": "QuantWikiBot/2.0"}
TOPVIEWS_URL = (
    f"{REST}/metrics/pageviews/top/en.wikipedia/all-access/{{yyyy}}/{{mm}}/{{dd}}"
)

# --- Momentum Config ---
TOP_N = 15
PRICE_LOOKBACK_SHORT = 5
PRICE_LOOKBACK_LONG = 20
MOM_BLEND_WEIGHTS = (0.6, 0.4)
SCORE_WEIGHTS = dict(momentum=0.7, z=0.3)
PERIOD = "2mo"
TICKER_BATCH = 50
PCT_CLIP = (1, 99)


CACHE_FILE = Path(__file__).resolve().parents[1] / "cache" / "wiki_index_map.csv"


@functools.lru_cache(maxsize=1)
def index_map() -> Dict[str, str]:
    """Return {symbol: company_name} for S&P 500 and S&P 400 constituents.

    Results are cached to ``cache/wiki_index_map.csv`` so subsequent runs avoid
    repeated network calls to yfinance. Missing entries are fetched in parallel
    to reduce startup latency.
    """

    syms = set(load_sp500()) | set(load_sp400())
    mapping: Dict[str, str] = {}

    if CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE)
        mapping = dict(zip(df.symbol, df.name))

    missing = sorted(s for s in syms if s not in mapping)
    if missing:
        _log.info("index_map fetching %d symbols", len(missing))

        def _fetch(sym: str) -> Tuple[str, str]:
            try:
                return sym, yf.Ticker(sym).info.get("shortName") or sym
            except Exception:
                return sym, sym

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for sym, name in ex.map(_fetch, missing):
                mapping[sym] = name

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(mapping.items(), columns=["symbol", "name"]).to_csv(
            CACHE_FILE, index=False
        )
    else:
        _log.info("index_map loaded %d symbols from cache", len(mapping))

    return mapping


def wiki_title(name: str) -> Optional[str]:
    wikipedia.set_lang("en")
    try:
        return wikipedia.page(name, auto_suggest=False).title.replace(" ", "_")
    except wikipedia.exceptions.PageError:
        hits = wikipedia.search(name, results=1)
        return hits[0].replace(" ", "_") if hits else None
    except Exception:
        return None


def fetch_views(page: str, days: int = 185) -> List[int]:
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    url = (
        f"{REST}/metrics/pageviews/per-article/en.wikipedia/all-access/"
        f"all-agents/{page}/daily/{start:%Y%m%d}/{end:%Y%m%d}"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return [row["views"] for row in r.json()["items"]]


@functools.lru_cache(maxsize=None)
def cached_views(page: str) -> pd.Series:
    v = fetch_views(page, 185)
    idx = pd.date_range(dt.date.today() - dt.timedelta(days=len(v)), periods=len(v))
    return pd.Series(v, index=idx[-len(v) :])


def z_score(series: pd.Series) -> float:
    return float(
        (series.tail(7).mean() - series.tail(30).mean()) / (series.tail(30).std() or 1)
    )


def persistence(series: pd.Series) -> float:
    return series.tail(30).sum() / max(series.tail(126).sum(), 1)


def _fetch_topviews(day: dt.date) -> List[dict]:
    url = TOPVIEWS_URL.format(yyyy=day.year, mm=f"{day.month:02}", dd=f"{day.day:02}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["items"][0]["articles"]


def _looks_like_company(title: str) -> bool:
    t = unidecode(title.lower())
    return any(k in t for k in ("inc", "corp", "company", "ltd", "plc", "group"))


def _ticker_from_wikidata(title: str) -> Optional[Tuple[str, str]]:
    html = requests.get(f"{REST}/page/html/{title}", headers=HEADERS, timeout=20).text
    m = re.search(r'data-wikidata-entity-id="(Q\d+)"', html)
    if not m:
        return None
    entity = m.group(1)
    data = requests.get(
        f"https://www.wikidata.org/wiki/Special:EntityData/{entity}.json", timeout=20
    ).json()
    try:
        claims = data["entities"][entity]["claims"]
        ticker = claims["P414"][0]["qualifiers"]["P249"][0]["datavalue"]["value"]
        company = data["entities"][entity]["labels"]["en"]["value"]
        return ticker.upper(), company
    except Exception:
        return None


async def trending_candidates(min_views: int = 3_000) -> Dict[str, str]:
    """Return {symbol: company} from yesterday's top-viewed list.

    Only tickers present in the combined index universe are included.
    """

    # Wikimedia topviews are occasionally missing for the most recent day.
    # Walk backwards up to a week until data is available to avoid hard
    # failures when yesterday's snapshot has not been published yet.
    last_exc: Exception | None = None
    for delta in range(1, 8):
        day = dt.date.today() - dt.timedelta(days=delta)
        try:
            arts = await asyncio.to_thread(_fetch_topviews, day)
            break
        except Exception as e:  # pragma: no cover - network optional
            last_exc = e
    else:
        _log.warning("Topviews fetch failed: %s", last_exc)
        return {}

    allowed = await asyncio.to_thread(index_map)
    out: Dict[str, str] = {}
    tasks = []
    for art in arts:
        if art["views"] < min_views:
            break
        title = art["article"]
        if not _looks_like_company(title):
            continue
        tasks.append(asyncio.to_thread(_ticker_from_wikidata, title))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if not res or isinstance(res, Exception):
            continue
        sym, name = res
        if sym in allowed:
            out[sym] = name

    return out


@functools.lru_cache(maxsize=None)
def adv_float(sym: str) -> Tuple[float, float]:
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="1mo")["Close"] * tk.history(period="1mo")["Volume"]
        adv = hist.mean()
        float_mcap = (
            tk.info.get("floatShares", 0) * tk.history(period="1d")["Close"].iloc[-1]
        )
        return float(adv or 0), float(float_mcap or 0)
    except Exception:
        return 0.0, 0.0


@functools.lru_cache(maxsize=None)
def sector_of(sym: str) -> str:
    try:
        return yf.Ticker(sym).info.get("sector", "Other")
    except Exception:
        return "Other"


def sector_weights(series: pd.Series) -> Dict[str, float]:
    return series.groupby(sector_of).sum().to_dict()


def robust_minmax(s: pd.Series, pct_clip: tuple[int, int] = PCT_CLIP) -> pd.Series:
    s = s.astype(float)
    lo, hi = np.nanpercentile(s, pct_clip[0]), np.nanpercentile(s, pct_clip[1])
    s = s.clip(lo, hi)
    span = hi - lo if hi > lo else 1.0
    return (s - lo) / span


def _extract_price_frame(raw: pd.DataFrame | pd.Series | None) -> pd.DataFrame:
    closes, _ = extract_close_volume(raw)
    return closes


def get_momentum_returns(tickers: list[str]) -> pd.DataFrame:
    results = {}
    for i in range(0, len(tickers), TICKER_BATCH):
        batch = tickers[i : i + TICKER_BATCH]
        try:
            raw = yf.download(batch, period=PERIOD, auto_adjust=True, progress=False)
            px = _extract_price_frame(raw)
        except Exception:
            continue
        if px.empty:
            continue
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
            ret5 = last / p5 - 1
            ret20 = last / p20 - 1
            momentum = MOM_BLEND_WEIGHTS[0] * ret20 + MOM_BLEND_WEIGHTS[1] * ret5
            results[t] = dict(ret_5d=ret5, ret_20d=ret20, momentum=momentum)
    return pd.DataFrame.from_dict(results, orient="index")


def build_wiki_portfolio(
    df_base: pd.DataFrame, top_n: int = TOP_N
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank tickers by momentum blended with Wikipedia z-score.

    Parameters
    ----------
    df_base : pd.DataFrame
        Must contain ``ticker`` and ``z_score`` columns for the universe.
    top_n : int
        Number of names to return.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        ``(top, full)`` ranked DataFrames.
    """

    required = {"ticker", "z_score"}
    missing = required - set(df_base.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    base = df_base.copy()
    base["ticker"] = base["ticker"].str.upper()
    tickers = base["ticker"].unique().tolist()

    mom = get_momentum_returns(tickers)
    if mom.empty:
        raise RuntimeError("No momentum data retrieved.")

    merged = base.merge(mom, left_on="ticker", right_index=True, how="left")
    merged = merged.dropna(subset=["momentum"])

    merged["mom_norm"] = robust_minmax(merged["momentum"])
    merged["z_norm"] = robust_minmax(merged["z_score"])

    merged["score"] = (
        SCORE_WEIGHTS["momentum"] * merged["mom_norm"]
        + SCORE_WEIGHTS["z"] * merged["z_norm"]
    )

    merged = merged.sort_values("score", ascending=False)
    top = merged.head(top_n).copy()
    top["weight_score"] = top["score"] / top["score"].sum()
    top["weight_equal"] = 1.0 / len(top)

    cols = [
        "ticker",
        "score",
        "weight_score",
        "weight_equal",
        "momentum",
        "ret_5d",
        "ret_20d",
        "z_score",
    ]
    return top[cols].reset_index(drop=True), merged
