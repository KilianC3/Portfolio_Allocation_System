from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Iterable, cast

import pandas as pd
import yfinance as yf

from database import (
    pf_coll,
    metric_coll,
    trade_coll,
    ticker_score_coll,
    top_score_coll,
    weight_coll,
)
from analytics.utils import portfolio_metrics
from scrapers.universe import load_sp500, load_sp400, load_russell2000
from analytics.fundamentals import compute_fundamental_metrics, yf_symbol
import numpy as np
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

log = get_logger(__name__)


def _fetch_returns(symbols: Iterable[str], days: int = 90) -> pd.DataFrame:
    """Download daily returns for the given symbols."""
    syms = list(symbols)
    if not syms:
        idx = pd.date_range(end=dt.date.today(), periods=days)
        return pd.DataFrame(index=idx)

    chunks = [syms[i : i + 200] for i in range(0, len(syms), 200)]
    closes = []
    for ch in chunks:
        df = yf.download(
            ch,
            period=f"{days + 1}d",
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(ch[0])
        closes.append(df)

    big = pd.concat(closes, axis=1)
    return big.pct_change().dropna()


def update_all_metrics(days: int = 90) -> None:
    """Compute trailing metrics for every portfolio."""
    log.info("update_all_metrics start")
    for doc in pf_coll.find():
        pf_id = str(doc.get("_id"))
        weights = doc.get("weights", {})
        rets = _fetch_returns(weights.keys(), days)
        if rets.empty:
            idx = pd.date_range(end=dt.date.today(), periods=days)
            series = pd.Series(0.0, index=idx)
        else:
            w = pd.Series(weights).reindex(rets.columns).fillna(0)
            series = (rets * w).sum(axis=1)
        metrics = portfolio_metrics(series)
        metrics["ret"] = float(series.iloc[-1]) if not series.empty else 0.0
        metrics["total_trades"] = trade_coll.count_documents({"portfolio_id": pf_id})
        end_date = (
            cast(pd.Timestamp, series.index[-1]).date()
            if not series.empty
            else dt.date.today()
        )
        metric_coll.update_one(
            {"portfolio_id": pf_id, "date": end_date},
            {"$set": metrics},
            upsert=True,
        )
        csv_dir = Path("cache") / "metrics"
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / f"{pf_id}.csv"
        header = not csv_path.exists()
        with csv_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["date", *metrics.keys()])
            if header:
                writer.writeheader()
            row = {"date": str(end_date), **metrics}
            writer.writerow(row)
        log.info(f"metrics updated for {pf_id}")


def _fetch_history(symbols: Iterable[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    syms = list(symbols)
    if not syms:
        idx = pd.date_range(end=dt.date.today(), periods=1)
        return pd.DataFrame(index=idx), pd.DataFrame(index=idx)

    yf_map = {yf_symbol(s): s for s in syms}
    df = yf.download(
        list(yf_map.keys()),
        period="13mo",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )
    closes = df["Close"]
    vols = df["Volume"] if "Volume" in df else None
    if isinstance(closes, pd.Series):
        key = list(yf_map.keys())[0]
        closes = closes.to_frame(key)
        vols = (
            vols.to_frame(key)
            if vols is not None
            else pd.DataFrame(index=closes.index, columns=[key])
        )
    closes = closes.rename(columns=yf_map)
    if vols is not None:
        vols = vols.rename(columns=yf_map)
    missing = [orig for yf_t, orig in yf_map.items() if yf_t not in closes.columns]
    for m in missing:
        log.warning(f"no price data for {m}")
    if vols is None:
        vols = pd.DataFrame(1.0, index=closes.index, columns=closes.columns)
    return closes.dropna(how="all"), vols.reindex(closes.index)


def _gather_metrics(symbols: Iterable[str], index_name: str) -> pd.DataFrame:
    """Return raw metric rows for the given symbols."""
    closes, vols = _fetch_history(symbols)
    if closes.empty:
        return pd.DataFrame()

    spx = (
        yf.download("^GSPC", period="13mo", interval="1d", progress=False)["Close"]
        .pct_change()
        .dropna()
    )
    today = dt.date.today()
    rows = []
    for sym in closes.columns:
        px = closes[sym].dropna()
        vol = vols[sym].reindex(px.index).ffill()
        r = px.pct_change().dropna()
        if r.empty:
            continue
        fund = compute_fundamental_metrics(sym)
        sharpe_1y = float(
            r.tail(252).mean() / (r.tail(252).std(ddof=0) or 1) * np.sqrt(252)
        )
        if len(spx) > 50:
            joined = pd.concat([r.tail(len(spx)), spx], axis=1).dropna()
            beta = (
                0.0
                if joined.var().iloc[1] == 0
                else joined.cov().iloc[0, 1] / joined.var().iloc[1]
            )
        else:
            beta = 0.0
        illiq = float((r.abs() / vol.tail(len(r))).replace(0, np.nan).mean())
        row = {
            "symbol": sym,
            "index_name": index_name,
            "date": today,
            "piotroski": fund.get("piotroski"),
            "altman": fund.get("altman"),
            "roic": fund.get("roic"),
            "fcf_yield": fund.get("fcf_yield"),
            "beneish": fund.get("beneish"),
            "ret_3m": float(px.iloc[-1] / px.iloc[-63] - 1) if len(px) > 62 else 0.0,
            "ret_6m": float(px.iloc[-1] / px.iloc[-126] - 1) if len(px) > 125 else 0.0,
            "ret_12m": (
                float(px.iloc[-22] / px.iloc[-273] - 1) if len(px) > 272 else 0.0
            ),
            "illiq": illiq,
            "short_ratio": fund.get("short_ratio"),
            "insider_buying": fund.get("insider_buying"),
            "sharpe": sharpe_1y,
            "beta": beta,
            "vol_1m": float(r.tail(21).std(ddof=0)),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def _compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Return dataframe with percentile-ranked composite scores."""
    if df.empty:
        return df

    def pct(col: str, invert: bool = False) -> pd.Series:
        series = df[col].fillna(0)
        p = series.rank(pct=True) * 100
        return 100 - p if invert else p

    df["fundamentals_score"] = (
        pct("piotroski") * 0.2
        + pct("altman") * 0.2
        + pct("roic") * 0.2
        + pct("fcf_yield") * 0.2
        + pct("beneish", invert=True) * 0.2
    )
    df["momentum_score"] = (pct("ret_3m") + pct("ret_6m") + pct("ret_12m")) / 3
    df["liq_sent_score"] = (
        pct("illiq", invert=True)
        + pct("short_ratio", invert=True)
        + pct("insider_buying")
    ) / 3
    df["risk_perf_score"] = (
        pct("sharpe") + pct("beta", invert=True) + pct("vol_1m", invert=True)
    ) / 3
    df["overall_score"] = (
        df["fundamentals_score"] * 0.376
        + df["momentum_score"] * 0.235
        + df["liq_sent_score"] * 0.07
        + df["risk_perf_score"] * 0.319
    )
    return df


def update_ticker_scores(symbols: Iterable[str], index_name: str) -> None:
    """Compute and store scores for the given symbols."""
    df = _gather_metrics(symbols, index_name)
    df = _compute_scores(df)
    if df.empty:
        return
    today = dt.date.today()
    for _, row in df.iterrows():
        doc = {
            "symbol": row["symbol"],
            "index_name": row["index_name"],
            "date": today,
            "score": float(row["overall_score"]),
        }
        ticker_score_coll.update_one(
            {"symbol": doc["symbol"], "date": today},
            {"$set": doc},
            upsert=True,
        )
    log.info("ticker scores updated")


def update_all_ticker_scores() -> None:
    """Update scores for the entire tracked universe."""
    log.info("update_all_ticker_scores start")
    groups = {
        "S&P500": set(load_sp500()),
        "S&P400": set(load_sp400()),
        "Russell2000": set(load_russell2000()),
    }
    frames: list[pd.DataFrame] = []
    for name, tickers in groups.items():
        symbols = sorted(tickers)
        for i in range(0, len(symbols), 200):
            chunk = symbols[i : i + 200]
            frames.append(_gather_metrics(chunk, name))

    all_rows = pd.concat(frames, ignore_index=True)
    scored = _compute_scores(all_rows)
    today = dt.date.today()
    for _, row in scored.iterrows():
        doc = {
            "symbol": row["symbol"],
            "index_name": row["index_name"],
            "date": today,
            "score": float(row["overall_score"]),
        }
        ticker_score_coll.update_one(
            {"symbol": doc["symbol"], "date": today},
            {"$set": doc},
            upsert=True,
        )
    log.info("update_all_ticker_scores done")
    record_top_scores()


def record_top_scores(top_n: int = 20) -> None:
    """Store the top ranked tickers for the latest score update."""
    latest = ticker_score_coll.find_one(sort=[("date", -1)])
    if not latest:
        return
    latest_date = latest["date"]
    cur = ticker_score_coll.find({"date": latest_date})
    df = pd.DataFrame(list(cur))
    if df.empty:
        return
    df = df.sort_values("score", ascending=False).head(top_n)
    top_score_coll.delete_many({"date": latest_date})
    for rank, row in enumerate(df.itertuples(index=False), 1):
        doc = {
            "date": latest_date,
            "symbol": row.symbol,
            "index_name": row.index_name,
            "score": float(row.score),
            "rank": rank,
        }
        top_score_coll.update_one(
            {"date": doc["date"], "symbol": doc["symbol"]},
            {"$set": doc},
            upsert=True,
        )
    log.info("top scores recorded")
