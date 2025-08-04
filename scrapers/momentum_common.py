from __future__ import annotations

from typing import List

import pandas as pd
import yfinance as yf


_CHUNK = 100


def _weekly_closes(tickers: list[str], weeks: int) -> pd.DataFrame:
    """Return weekly close prices for ``tickers``."""
    df = yf.download(
        tickers,
        period=f"{weeks + 1}wk",
        interval="1wk",
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs("Close", level=0, axis=1)
    return df.dropna(how="all")
