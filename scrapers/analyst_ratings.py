from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from typing import Iterable, List, Optional, Tuple, cast

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup, Tag

from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

analyst_coll = db["analyst_ratings"] if db else pf_coll
log = get_logger(__name__)

URL = "https://www.benzinga.com/analyst-stock-ratings/upgrades"

UPGRADE_TERMS = {
    "upgrade",
    "upgrades",
    "raises",
    "raised",
    "increase",
    "increases",
    "initiates",
    "reiterates",
    "maintains",
}
BULLISH_RATINGS = {
    "buy",
    "strong buy",
    "outperform",
    "overweight",
    "accumulate",
    "market outperform",
}

PT_CHANGE_THRESHOLD = 5.0
IMPORTANCE_MIN = 4
KEEP_NA_IMPORTANCE = False
MOMENTUM_DAYS = 7
TOP_N = 15
HEADERS = {"User-Agent": "Mozilla/5.0"}


def find_ratings_blob(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    scripts: List[Tag] = list(cast(Iterable[Tag], soup.find_all("script")))

    def search(obj: object) -> Optional[List[dict]]:
        if isinstance(obj, list):
            if obj and isinstance(obj[0], dict) and "rating_current" in obj[0]:
                if {"pt_current", "pt_prior"} & set(obj[0].keys()):
                    return obj  # type: ignore[return-value]
            for x in obj:
                r = search(x)
                if r:
                    return r
        elif isinstance(obj, dict):
            for v in obj.values():
                r = search(v)
                if r:
                    return r
        return None

    for sc in scripts:
        txt = sc.string or ""
        t = txt.strip()
        if not (t.startswith("{") or t.startswith("[")):
            continue
        try:
            j = json.loads(t)
        except Exception:
            continue
        blob = search(j)
        if blob:
            return blob
    raise RuntimeError("Ratings JSON blob not found")


def infer_ticker(rec: dict) -> str:
    for k in ("ticker", "symbol", "stock", "stock_symbol"):
        if k in rec and rec[k]:
            return str(rec[k]).strip().upper()
    for field in ("notes", "name"):
        val = rec.get(field) or ""
        m = re.findall(r"\b[A-Z]{1,5}\b", val)
        if m:
            banned = {"USD", "CEO", "EPS"}
            for cand in m:
                if cand not in banned:
                    return cand
    return ""


def fetch_upgrades(limit: int = 200) -> Tuple[pd.DataFrame, pd.DataFrame]:
    r = requests.get(URL, timeout=30, headers=HEADERS)
    r.raise_for_status()
    data = find_ratings_blob(r.text)
    rows: List[dict] = []
    for rec in data[:limit]:
        action = rec.get("action_company")
        company = rec.get("name")
        ticker = infer_ticker(rec)
        pt_prior = rec.get("pt_prior")
        pt_curr = rec.get("pt_current")
        pct = rec.get("pt_pct_change")
        try:
            if (
                (pct is None or pct == "" or str(pct).lower() == "nan")
                and pt_prior
                and pt_curr
            ):
                pt_prior_f = float(pt_prior)
                pt_curr_f = float(pt_curr)
                if pt_prior_f:
                    pct = (pt_curr_f - pt_prior_f) / pt_prior_f * 100
        except Exception:
            pct = None
        rows.append(
            {
                "date": rec.get("date"),
                "action": action,
                "company_name": company,
                "ticker": ticker,
                "analyst": rec.get("analyst_name") or rec.get("analyst"),
                "rating_current": rec.get("rating_current"),
                "pt_prior": pt_prior,
                "pt_current": pt_curr,
                "pt_pct_change": pct,
                "notes": rec.get("notes"),
                "importance": rec.get("importance"),
                "currency": rec.get("currency"),
                "exchange": rec.get("exchange"),
                "id": rec.get("id"),
            }
        )
    df = pd.DataFrame(rows)

    for c in ("pt_prior", "pt_current", "pt_pct_change", "importance"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["action_lower"] = df["action"].fillna("").str.lower()
    df["rating_lower"] = df["rating_current"].fillna("").str.lower()
    df["upgrade_action"] = df["action_lower"].apply(
        lambda x: any(t in x for t in UPGRADE_TERMS)
    )
    df["bullish_rating"] = df["rating_lower"].apply(
        lambda x: any(b in x for b in BULLISH_RATINGS)
    )
    df["significant_pt_move"] = df["pt_pct_change"].abs() >= PT_CHANGE_THRESHOLD

    signal = df[
        df["upgrade_action"] | df["bullish_rating"] | df["significant_pt_move"]
    ].copy()

    if KEEP_NA_IMPORTANCE:
        high_rated = signal[
            (signal["importance"].isna()) | (signal["importance"] >= IMPORTANCE_MIN)
        ]
    else:
        high_rated = signal[signal["importance"] >= IMPORTANCE_MIN]

    if not high_rated.empty:
        cutoff = None
        if high_rated["date"].notna().any():
            cutoff = high_rated["date"].max() - pd.Timedelta(days=MOMENTUM_DAYS)
        window_df = (
            high_rated if cutoff is None else high_rated[high_rated["date"] >= cutoff]
        )
        momentum_counts = window_df.groupby("ticker").size().rename("momentum_count")
        high_rated = high_rated.merge(momentum_counts, on="ticker", how="left")
    else:
        high_rated["momentum_count"] = 0

    high_rated["momentum_count"] = high_rated["momentum_count"].fillna(0).astype(int)
    high_rated["momentum_window_days"] = MOMENTUM_DAYS

    high_rated["abs_pt_move"] = high_rated["pt_pct_change"].abs()
    high_rated["score"] = high_rated["abs_pt_move"].fillna(0) * (
        1 + 0.15 * high_rated["momentum_count"]
    ) + 2 * high_rated["importance"].fillna(0)

    ranked = high_rated.sort_values(["score", "abs_pt_move"], ascending=False).head(
        TOP_N
    )

    display_cols = [
        "date",
        "ticker",
        "company_name",
        "action",
        "analyst",
        "rating_current",
        "pt_prior",
        "pt_current",
        "pt_pct_change",
        "importance",
        "momentum_count",
        "score",
    ]
    ranked = ranked[display_cols]
    return df, ranked


def _fetch_ticker(sym: str) -> pd.DataFrame:
    log.info(f"_fetch_ticker start sym={sym}")
    df, _ = fetch_upgrades(limit=200)
    if df.empty:
        return df
    df = df[df["ticker"].str.upper() == sym.upper()]
    df = df.dropna(subset=["date"])
    df = df.assign(rating="upgrade")[["date", "rating"]]
    log.info(f"fetched {len(df)} analyst rows for {sym}")
    return df


async def fetch_analyst_ratings(limit: int = 15) -> List[dict]:
    """Fetch latest analyst upgrades from Benzinga."""
    log.info("fetch_analyst_ratings start")
    init_db()
    with scrape_latency.labels("analyst_ratings").time():
        try:
            raw_df, _ = await asyncio.to_thread(fetch_upgrades, limit)
        except Exception as exc:
            scrape_errors.labels("analyst_ratings").inc()
            log.warning(f"fetch_analyst_ratings failed: {exc}")
            raise

    if raw_df.empty:
        return []

    now = dt.datetime.now(dt.timezone.utc)
    rows: List[dict] = []
    for _, row in raw_df.head(limit).iterrows():
        item = {
            "date_utc": row["date"].isoformat() if not pd.isna(row["date"]) else "",
            "ticker": row.get("ticker", ""),
            "company": row.get("company_name", ""),
            "analyst": row.get("analyst", ""),
            "rating_current": row.get("rating_current", ""),
            "pt_prior": row.get("pt_prior"),
            "pt_current": row.get("pt_current"),
            "pt_pct_change": row.get("pt_pct_change"),
            "importance": row.get("importance"),
            "notes": row.get("notes"),
            "action": row.get("action"),
            "_retrieved": now,
        }
        rows.append(item)

    append_snapshot("analyst_ratings", rows)
    log.info(f"fetched {len(rows)} analyst rows")
    return rows


async def fetch_changes(symbols: Iterable[str], weeks: int = 4) -> pd.DataFrame:
    cutoff = pd.Timestamp.today(tz=dt.timezone.utc) - pd.Timedelta(weeks=weeks)
    all_records = await fetch_analyst_ratings(limit=200)
    df = pd.DataFrame(all_records)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "upgrades",
                "downgrades",
                "total",
                "targetMeanPrice",
                "numAnalystOpinions",
            ]
        )
    df["date"] = pd.to_datetime(df["date_utc"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[df["date"] >= cutoff]
    rows: List[dict] = []
    for sym in symbols:
        sub = df[df["ticker"].str.upper() == sym.upper()]
        up = int(sub["action"].str.contains("UPGRADE").sum())
        info = {}
        try:
            info = yf.Ticker(sym).info
        except Exception:
            info = {}
        rows.append(
            dict(
                symbol=sym,
                upgrades=up,
                downgrades=0,
                total=len(sub),
                targetMeanPrice=info.get("targetMeanPrice"),
                numAnalystOpinions=info.get("numberOfAnalystOpinions"),
            )
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df_raw, df_top = fetch_upgrades(limit=300)
    if df_raw is None:
        df = pd.DataFrame()
    else:
        df = df_top if not df_top.empty else df_raw
    cols = df.shape[1] if not df.empty else 0
    print(f"ROWS={len(df)} COLUMNS={cols}")
