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
    ticker_return_coll,
    weight_coll,
)
from analytics.utils import portfolio_metrics
from scrapers.universe import (
    load_sp500,
    load_sp400,
    load_sp600,
    load_russell2000,
)


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


def update_ticker_returns(symbols: Iterable[str], index_name: str) -> None:
    """Fetch close prices and compute multi-horizon returns."""
    sym_list = list(symbols)
    if not sym_list:
        return

    df = yf.download(
        sym_list,
        period="5y",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )["Close"]

    if isinstance(df, pd.Series):
        df = df.to_frame(sym_list[0])

    today = dt.date.today()
    for sym in df.columns:
        series = df[sym].dropna()
        if series.empty:
            continue
        metrics = {
            "symbol": sym,
            "index_name": index_name,
            "date": today,
            "ret_7d": (
                float(series.iloc[-1] / series.iloc[-8] - 1) if len(series) > 7 else 0.0
            ),
            "ret_1m": (
                float(series.iloc[-1] / series.iloc[-22] - 1)
                if len(series) > 21
                else 0.0
            ),
            "ret_3m": (
                float(series.iloc[-1] / series.iloc[-63] - 1)
                if len(series) > 62
                else 0.0
            ),
            "ret_6m": (
                float(series.iloc[-1] / series.iloc[-126] - 1)
                if len(series) > 125
                else 0.0
            ),
            "ret_1y": (
                float(series.iloc[-1] / series.iloc[-252] - 1)
                if len(series) > 251
                else 0.0
            ),
            "ret_2y": (
                float(series.iloc[-1] / series.iloc[-504] - 1)
                if len(series) > 503
                else 0.0
            ),
            "ret_5y": float(series.iloc[-1] / series.iloc[0] - 1),
        }
        ticker_return_coll.update_one(
            {"symbol": sym, "date": today},
            {"$set": metrics},
            upsert=True,
        )


def update_all_ticker_returns() -> None:
    """Update returns for the entire tracked universe."""
    groups = {
        "S&P500": set(load_sp500()),
        "S&P400": set(load_sp400()),
        "S&P600": set(load_sp600()),
        "Russell2000": set(load_russell2000()),
    }
    for name, tickers in groups.items():
        batch: list[str] = []
        for sym in sorted(tickers):
            batch.append(sym)
            if len(batch) >= 200:
                update_ticker_returns(batch, name)
                batch.clear()
        if batch:
            update_ticker_returns(batch, name)
