from core.equity import EquityPortfolio

class RedditBuzzStrategy:
    async def build(self, pf: EquityPortfolio):
        pf.set_weights({"SPY": 1.0})
        await pf.rebalance()
