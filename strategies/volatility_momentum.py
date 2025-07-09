from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from core.equity import EquityPortfolio


class VolatilityScaledMomentum:
    """Momentum strategy with volatility scaling."""

    def __init__(
        self, universe: Iterable[str], n: int = 5, long_only: bool = False
    ) -> None:
        self.universe = list(universe)
        self.n = n
        self.long_only = long_only

    def _fetch_prices(self) -> pd.DataFrame:
        import yfinance as yf

        df = yf.download(
            self.universe,
            period="13mo",
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(self.universe[0])
        return df.dropna(how="all")

    def _rank(self, prices: pd.DataFrame) -> pd.DataFrame:
        ret_12m = prices.iloc[-1] / prices.iloc[0] - 1
        vol_60 = prices.pct_change().tail(60).std() * math.sqrt(252)
        score = ret_12m / vol_60.replace(0, float("nan"))
        ranks = pd.DataFrame({"ret": ret_12m, "vol": vol_60, "score": score})
        return ranks.sort_values("score", ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        prices = self._fetch_prices()
        if prices.empty:
            return
        ranks = self._rank(prices)
        longs = ranks.head(self.n)
        shorts = pd.DataFrame() if self.long_only else ranks.tail(self.n)
        weights = {}
        if not longs.empty:
            inv_vol = 1 / longs["vol"]
            w = inv_vol / inv_vol.sum()
            if self.long_only:
                weights.update(w.to_dict())
            else:
                weights.update((w / 2).to_dict())
        if not shorts.empty:
            inv_vol = 1 / shorts["vol"]
            w = inv_vol / inv_vol.sum()
            weights.update({k: -v / 2 for k, v in w.to_dict().items()})
        if weights:
            pf.set_weights(weights)
            await pf.rebalance()
