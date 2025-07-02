from portfolio import Portfolio
class LobbyingGrowthStrategy:
    async def build(self,pf:Portfolio):
        pf.set_weights({"AAPL":1.0})
        pf.rebalance()
