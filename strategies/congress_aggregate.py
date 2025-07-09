from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import politician_coll


class CongressionalTradingAggregate:
    """Long names with net congressional buying over the last month."""

    def __init__(self, top_n: int = 20) -> None:
        self.top_n = top_n

    def _rank(self) -> pd.Series:
        docs = list(politician_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = (
            df["amount"].str.replace("$", "").str.replace(",", "").astype(float)
        )
        df = df.dropna(subset=["date", "amount"])
        cutoff = df["date"].max() - pd.Timedelta(days=30)
        df = df[df["date"] >= cutoff]
        sign = df["transaction"].str.lower().map(lambda x: -1 if "sell" in x else 1)
        agg = (df["amount"] * sign).groupby(df["ticker"]).sum()
        return agg.sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = self._rank().head(self.top_n)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
