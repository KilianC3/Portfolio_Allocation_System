from __future__ import annotations

from core.equity import EquityPortfolio
from scripts.wsb_strategy import run_analysis


class RedditBuzzStrategy:
    """Long symbols with the fastest rise in r/WallStreetBets mentions."""

    def __init__(self, days: int = 7, top_n: int = 15) -> None:
        self.days = days
        self.top_n = top_n

    async def build(self, pf: EquityPortfolio) -> None:
        df = run_analysis(self.days, self.top_n)
        if df.empty:
            return
        w = {sym: 1 / len(df) for sym in df["symbol"]}
        pf.set_weights(w)
        await pf.rebalance()
