from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import google_trends_coll as trends_coll


class GoogleTrendsNewsSentiment:
    """Long tickers with rising search interest and positive news."""

    def __init__(self, top_n: int = 30) -> None:
        self.top_n = top_n

    def _rank(self) -> pd.Series:
        docs = list(trends_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["score", "date"])
        latest = df["date"].max()
        cutoff = latest - pd.Timedelta(days=30)
        df = df[df["date"] >= cutoff]
        score = df.groupby("ticker")["score"].mean()
        return score.sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = self._rank().head(self.top_n)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
