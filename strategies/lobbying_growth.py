from core.equity import EquityPortfolio

class LobbyingGrowthStrategy:
    async def build(self, pf: EquityPortfolio):
        pf.set_weights({"AAPL":1.0})
        pf.rebalance()
