from __future__ import annotations

import pandas as pd
import yfinance as yf

from core.equity import EquityPortfolio

DEFAULT_TICKERS = ["UPRO", "SOXL", "SPXL", "FAS", "LABU", "TQQQ"]


class LeveragedSectorMomentum:
    """Momentum rotation among leveraged sector ETFs."""

    def __init__(self, tickers=None) -> None:
        self.tickers = tickers or DEFAULT_TICKERS

    def _fetch_prices(self) -> pd.DataFrame:
        df = yf.download(
            self.tickers,
            period="6mo",
            interval="1wk",
            group_by="ticker",
            threads=True,
            progress=False,
        )["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(self.tickers[0])
        return df.dropna(how="all")

    def _rank(self, prices: pd.DataFrame) -> pd.Series:
        if len(prices) < 13:
            return pd.Series(dtype=float)
        ret = prices.iloc[-1] / prices.iloc[-13] - 1
        return ret.sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        prices = self._fetch_prices()
        ranks = self._rank(prices)
        top = ranks.head(3).index
        if not len(top):
            return
        w = {sym: 1 / len(top) for sym in top}
        pf.set_weights(w)
        await pf.rebalance()
