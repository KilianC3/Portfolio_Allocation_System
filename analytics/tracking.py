from __future__ import annotations

import datetime as dt
from typing import Iterable

import pandas as pd
import yfinance as yf

from typing import cast

from database import pf_coll, metric_coll
from analytics_utils import portfolio_metrics


def _fetch_returns(symbols: Iterable[str], days: int = 90) -> pd.DataFrame:
    """Download daily returns for the given symbols."""
    syms = list(symbols)
    if not syms:
        idx = pd.date_range(end=dt.date.today(), periods=days)
        return pd.DataFrame(index=idx)
    df = yf.download(
        syms,
        period=f"{days + 1}d",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(syms[0])
    rets = df.pct_change().dropna()
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
        end_date = cast(pd.Timestamp, series.index[-1]).date()
        metric_coll.update_one(
            {"portfolio_id": pf_id, "date": end_date},
            {"$set": {"ret": float(series.iloc[-1]), **metrics}},
            upsert=True,
        )
