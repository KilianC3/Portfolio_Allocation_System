from __future__ import annotations

import math
from typing import Sequence

import pandas as pd
import numpy as np
import yfinance as yf

from core.equity import EquityPortfolio

SECTOR_ETFS = [
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLRE",
    "XLU",
    "XLV",
    "XLY",
    "XLC",
]


class SectorRiskParityMomentum:
    """Risk-parity momentum rotation across S&P 500 sector ETFs."""

    def __init__(
        self, tickers: Sequence[str] = SECTOR_ETFS, target_vol: float = 0.10
    ) -> None:
        self.tickers = list(tickers)
        self.target_vol = target_vol

    def _fetch_prices(self) -> pd.DataFrame:
        df = yf.download(
            self.tickers,
            period="1y",
            interval="1wk",
            group_by="ticker",
            threads=True,
            progress=False,
        )["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(self.tickers[0])
        return df.dropna(how="all")

    def _rank(self, prices: pd.DataFrame) -> pd.Series:
        if len(prices) < 26:
            return pd.Series(dtype=float)
        ret = prices.iloc[-1] / prices.iloc[-26] - 1
        return ret.sort_values(ascending=False)

    @staticmethod
    def _risk_parity(returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
        cov = returns.cov()
        vol = returns.std().replace(0, np.nan)
        w = 1 / vol
        w = w / w.sum()
        return w, cov

    def _vol_target(self, w: pd.Series, cov: pd.DataFrame) -> pd.Series:
        port_vol = math.sqrt(float(w @ (cov * 52) @ w))
        if port_vol == 0:
            return w
        k = min(1.5, self.target_vol / port_vol)
        return w * k

    async def build(self, pf: EquityPortfolio) -> None:
        prices = self._fetch_prices()
        ranks = self._rank(prices)
        top = ranks.head(3).index.tolist()
        if not top:
            return
        rets = prices[top].pct_change().dropna().tail(4)
        if rets.empty:
            return
        w, cov = self._risk_parity(rets)
        w = self._vol_target(w, cov)
        pf.set_weights(w.to_dict())
        await pf.rebalance()
