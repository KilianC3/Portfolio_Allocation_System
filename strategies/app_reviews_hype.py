from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import app_reviews_coll


class AppReviewsHypeScore:
    """Long names with the biggest jump in app-review hype."""

    def __init__(self, top_n: int = 20) -> None:
        self.top_n = top_n

    def _rank(self) -> pd.Series:
        docs = list(app_reviews_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["hype"] = pd.to_numeric(df["hype"], errors="coerce")
        df = df.dropna(subset=["date", "hype"])
        latest = df["date"].max()
        prev_week = latest - pd.Timedelta(days=7)
        last = df[df["date"] >= prev_week]
        prev = df[df["date"] < prev_week]
        chg = (
            last.groupby("ticker")["hype"].mean()
            - prev.groupby("ticker")["hype"].mean()
        )
        return chg.dropna().sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = self._rank().head(self.top_n)
        if ranks.empty:
            return
        w = {sym: 1 / len(ranks) for sym in ranks.index}
        pf.set_weights(w)
        await pf.rebalance()
