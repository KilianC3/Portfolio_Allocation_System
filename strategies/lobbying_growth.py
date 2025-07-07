from __future__ import annotations

import pandas as pd
from core.equity import EquityPortfolio
from database import lobby_coll


class LobbyingGrowthStrategy:
    """Long companies with the largest increase in lobbying spend."""

    def __init__(self, top_n: int = 20) -> None:
        self.top_n = top_n

    def _fetch(self) -> pd.DataFrame:
        docs = list(lobby_coll.find())
        if not docs:
            return pd.DataFrame()
        df = pd.DataFrame(docs)
        df["amount"] = (
            df["amount"].str.replace("$", "").str.replace(",", "").astype(float)
        )
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "amount"])
        latest = df["date"].max()
        cutoff = latest - pd.Timedelta(days=60)
        return df[df["date"] >= cutoff]

    def _rank(self, df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)
        recent = df[df["date"] >= df["date"].max() - pd.Timedelta(days=30)]
        prior = df[df["date"] < df["date"].max() - pd.Timedelta(days=30)]
        last_sum = recent.groupby("ticker")["amount"].sum()
        prev_sum = prior.groupby("ticker")["amount"].sum()
        growth = (last_sum - prev_sum).div(prev_sum.replace(0, pd.NA))
        return growth.dropna().sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        df = self._fetch()
        ranks = self._rank(df).head(self.top_n)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
