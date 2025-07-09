from __future__ import annotations

import datetime as dt
from typing import Iterable

import pandas as pd
import yfinance as yf

from typing import cast

from database import pf_coll, metric_coll
from analytics.utils import portfolio_metrics, period_return
from pathlib import Path
import csv


def _fetch_returns(symbols: Iterable[str], days: int = 90) -> pd.DataFrame:
    """Download daily returns for the given symbols.

    Large universes are fetched in chunks so that the Yahoo API
    does not fail when requesting thousands of tickers at once.
    """

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
    rets = big.pct_change().dropna()
    return rets


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
        metrics["ret_7d"] = period_return(series, 7)
        metrics["ret_30d"] = period_return(series, 30)
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
        # append to CSV
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
