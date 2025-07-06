import asyncio
import pandas as pd
import numpy as np

from strategies.leveraged_sector import LeveragedSectorMomentum


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


async def _run():
    strat = LeveragedSectorMomentum(["A", "B", "C", "D"])
    prices = pd.DataFrame({
        "A": np.linspace(1, 2, 70),
        "B": np.linspace(1, 3, 70),
        "C": np.linspace(1, 1.5, 70),
        "D": np.linspace(1, 4, 70),
    })
    strat._fetch_prices = lambda: prices
    pf = DummyPF()
    await strat.build(pf)
    return pf.weights


def test_leveraged_weights():
    weights = asyncio.run(_run())
    assert set(weights) == {"B", "D", "A"}
    assert all(abs(v - 1/3) < 1e-6 for v in weights.values())

