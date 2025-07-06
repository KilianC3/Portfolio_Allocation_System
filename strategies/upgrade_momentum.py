from __future__ import annotations

from collections import deque
from typing import Iterable

import pandas as pd

from core.equity import EquityPortfolio
from scrapers.analyst_ratings import fetch_changes


class UpgradeMomentumStrategy:
    """Analyst upgrade momentum with turnover smoothing."""

    def __init__(self, universe: Iterable[str]):
        self.universe = list(universe)
        self.history: deque[pd.Series] = deque(maxlen=8)

    async def _rank(self) -> pd.DataFrame:
        df = await fetch_changes(self.universe, weeks=4)
        if df.empty:
            return df
        df["ratio"] = (df["upgrades"] - df["downgrades"]) / df["total"].replace(0, pd.NA)
        return df.dropna(subset=["ratio"]).sort_values("ratio", ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = await self._rank()
        if ranks.empty:
            return
        decile = max(1, len(ranks) // 10)
        winners = ranks.head(decile)["symbol"]
        w = pd.Series(1 / decile, index=winners)
        self.history.append(w)
        avg = pd.concat(list(self.history), axis=1).mean(axis=1)
        weights = (avg / avg.sum()).to_dict()
        pf.set_weights(weights)
        await pf.rebalance()
