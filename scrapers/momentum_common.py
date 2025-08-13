from __future__ import annotations

from typing import List

import datetime as dt
import pandas as pd
import yfinance as yf


_CHUNK = 100


def _weekly_closes(tickers: list[str], weeks: int) -> pd.DataFrame:
    """Return weekly close prices for ``tickers``.

    The previous implementation relied on yfinance's ``period`` argument with
    values like ``"26wk"`` which are not supported by the API and resulted in
    empty downloads.  Fetch data using explicit ``start`` and ``end`` dates so
    all momentum scrapers receive the expected price history.  Recent versions
    of yfinance also changed the default ``auto_adjust`` flag which removed the
    raw ``Close`` column, breaking our downstream ratio calculations.  Explicitly
    disable adjustment and corporate action handling so the returned frame always
    contains unadjusted close prices.
    """

    end = dt.date.today()
    start = end - dt.timedelta(weeks=weeks + 1)
    df = yf.download(
        tickers,
        start=start,
        end=end + dt.timedelta(days=1),
        interval="1wk",
        group_by="column",
        threads=True,
        progress=False,
        auto_adjust=False,
        actions=False,
    )
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs("Close", level=0, axis=1)
    return df.dropna(how="all")
