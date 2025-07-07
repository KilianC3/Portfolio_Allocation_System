import asyncio
import pandas as pd
import numpy as np

from strategies.sector_momentum import SectorRiskParityMomentum


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


async def _run():
    strat = SectorRiskParityMomentum(["A", "B", "C", "D"])
    prices = pd.DataFrame(
        {
            "A": np.linspace(1, 2, 150),
            "B": np.linspace(1, 3, 150),
            "C": np.linspace(1, 1.5, 150),
            "D": np.linspace(1, 4, 150),
        }
    )
    strat._fetch_prices = lambda: prices
    pf = DummyPF()
    await strat.build(pf)
    return pf.weights


def test_sector_weights():
    weights = asyncio.run(_run())
    assert set(weights) == {"A", "B", "D"}
    assert all(v >= 0 for v in weights.values())
