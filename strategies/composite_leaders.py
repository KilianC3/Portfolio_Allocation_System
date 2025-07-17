from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import top_score_coll


class CompositeScoreLeaders:
    """Equal-weight top composite score stocks."""

    def __init__(self, top_n: int = 20) -> None:
        self.top_n = top_n

    def _select(self) -> pd.Index:
        doc = top_score_coll.find_one(sort=[("date", -1)])
        if not doc:
            return pd.Index([])
        latest = doc["date"]
        rows = list(top_score_coll.find({"date": latest}).limit(self.top_n))
        if not rows:
            return pd.Index([])
        df = pd.DataFrame(rows)
        return df.sort_values("rank")["symbol"].reset_index(drop=True)

    async def build(self, pf: EquityPortfolio) -> None:
        tickers = self._select()
        if tickers.empty:
            return
        w = {sym: 1 / len(tickers) for sym in tickers}
        pf.set_weights(w)
        await pf.rebalance()
