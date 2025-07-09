from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import insider_buy_coll


class CorporateInsiderBuyingPulse:
    """Long names with strong executive buying."""

    def __init__(self, top_n: int = 25) -> None:
        self.top_n = top_n

    def _rank(self) -> pd.Series:
        docs = list(insider_buy_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["shares"] = pd.to_numeric(df["shares"].str.replace(",", ""), errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "shares"])
        cutoff = df["date"].max() - pd.Timedelta(days=30)
        recent = df[df["date"] >= cutoff]
        agg = recent.groupby("ticker")["shares"].sum()
        return agg.sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = self._rank().head(self.top_n)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
