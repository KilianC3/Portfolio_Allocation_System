from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import politician_coll


class FollowTheLeaderSleeves:
    """Replicate trades for selected politicians."""

    def __init__(self, leaders: list[str]):
        self.leaders = [l.lower() for l in leaders]

    def _rank(self) -> pd.Series:
        docs = list(politician_coll.find({"politician": {"$in": self.leaders}}))
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
        ranks = self._rank().head(10)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
