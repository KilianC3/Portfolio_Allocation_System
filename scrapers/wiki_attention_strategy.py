from __future__ import annotations

import datetime as dt
import functools
import logging
import math
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests  # type: ignore[import-untyped]
import wikipedia
import yfinance as yf
from tqdm import tqdm
from unidecode import unidecode

_log = logging.getLogger("scrapers.wiki_attention")
_log.setLevel(logging.INFO)

REST = "https://wikimedia.org/api/rest_v1"
HEADERS = {"User-Agent": "QuantWikiBot/2.0"}
SP1500_URL = "https://en.wikipedia.org/wiki/S%26P_1500"
TOPVIEWS_URL = f"{REST}/metrics/pageviews/top/en.wikipedia/all-access/{{yyyy}}/{{mm}}/{{dd}}"


@functools.lru_cache(maxsize=1)
def sp1500_map() -> Dict[str, str]:
    """Return {symbol: company_name} for S&P 1500 (cached)."""
    _log.info("Fetching S&P 1500 constituents …")
    html = requests.get(SP1500_URL, headers=HEADERS, timeout=30).text
    dfs = pd.read_html(html)
    big = pd.concat(dfs[:3])
    big.columns = big.columns.str.lower()
    return dict(zip(big["ticker"], big["security"]))


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
    return float((series.tail(7).mean() - series.tail(30).mean()) / (series.tail(30).std() or 1))


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


def trending_candidates(min_views: int = 3_000) -> Dict[str, str]:
    """Return {symbol: company} from yesterday's top-viewed list."""
    yday = dt.date.today() - dt.timedelta(days=1)
    try:
        arts = _fetch_topviews(yday)
    except Exception as e:
        _log.warning("Topviews fetch failed: %s", e)
        return {}
    out = {}
    for art in arts:
        if art["views"] < min_views:
            break
        title = art["article"]
        if not _looks_like_company(title):
            continue
        tup = _ticker_from_wikidata(title)
        if tup:
            sym, name = tup
            out[sym] = name
    return out


@functools.lru_cache(maxsize=None)
def adv_float(sym: str) -> Tuple[float, float]:
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="1mo")["Close"] * tk.history(period="1mo")["Volume"]
        adv = hist.mean()
        float_mcap = tk.info.get("floatShares", 0) * tk.history(period="1d")["Close"].iloc[-1]
        return float(adv or 0), float(float_mcap or 0)
    except Exception:
        return 0.0, 0.0


@functools.lru_cache(maxsize=1)
def sector_table() -> pd.DataFrame:
    t = pd.read_html(SP1500_URL)[0]
    t.columns = [c.lower() for c in t.columns]
    return t.set_index("symbol")["gics sector"]


def sector_of(sym: str) -> str:
    tbl = sector_table()
    return tbl.get(sym, "Other")


def sector_weights(series: pd.Series) -> Dict[str, float]:
    return series.groupby(sector_of).sum().to_dict()


def build_wiki_portfolio(
    *,
    universe: Dict[str, str] | None = None,
    include_trending: bool = True,
    top_k: int = 50,
    min_adv_usd: float = 3_000_000,
    min_float_usd: float = 500_000_000,
    turnover_thresh: float = 0.005,
    alpha_power: float = 0.7,
    prev_weights: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Build weights for the Wikipedia Most-Viewed strategy."""
    uni = universe or sp1500_map()
    if include_trending:
        uni.update(trending_candidates())

    rows = []
    for sym, name in tqdm(uni.items(), desc="views", unit="stk", leave=False):
        page = wiki_title(name)
        if not page:
            continue
        series = cached_views(page)
        if len(series) < 185:
            continue
        score = z_score(series) * persistence(series)
        rows.append(
            dict(
                symbol=sym,
                company=name,
                score=score,
                views_30d=int(series.tail(30).sum()),
                sector=sector_of(sym),
                source="universe" if sym in sp1500_map() else "trending",
            )
        )

    df = pd.DataFrame(rows).sort_values("score", ascending=False).head(top_k)
    if df.empty:
        _log.warning("No candidates after score ranking.")
        return df

    keep = []
    for sym in tqdm(df.symbol, desc="liquidity", leave=False):
        adv, float_cap = adv_float(sym)
        if adv >= min_adv_usd and float_cap >= min_float_usd:
            keep.append(sym)
    df = df[df.symbol.isin(keep)]
    if df.empty:
        _log.warning("Liquidity filter removed all names.")
        return df

    w_raw = df.views_30d.astype(float).pow(alpha_power)
    df["w_raw"] = w_raw / w_raw.sum()

    bench = sector_weights(pd.Series({**{s: 1 for s in sp1500_map()}, **{}}))
    sec = sector_weights(df.set_index("symbol").w_raw)
    for sector, w_sect in sec.items():
        bench_w = bench.get(sector, 0)
        diff = w_sect - bench_w
        if abs(diff) > 0.05:
            factor = (bench_w + math.copysign(0.05, diff)) / w_sect
            df.loc[df.sector == sector, "w_raw"] *= factor
    df["w_raw"] /= df.w_raw.sum()

    if prev_weights is not None and not prev_weights.empty:
        merged = df.set_index("symbol").join(prev_weights.rename("prev"), how="outer")
        delta = (merged.w_raw.fillna(0) - merged.prev.fillna(0)).abs()
        merged.loc[delta <= turnover_thresh, "w_raw"] = merged.prev
        df = merged.reset_index()

    df["weight"] = df.w_raw / df.w_raw.sum()
    return df[["symbol", "weight", "score", "views_30d", "sector", "source"]]
