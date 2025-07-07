import os
import asyncio
import pandas as pd
import numpy as np

os.environ["PG_URI"] = "postgresql://localhost/test"

from strategies.volatility_momentum import VolatilityScaledMomentum


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


async def _run():
    strat = VolatilityScaledMomentum(["A", "B", "C"], n=1, long_only=True)
    prices = pd.DataFrame(
        {
            "A": np.linspace(1, 2, 260),
            "B": np.linspace(1, 1.2, 260),
            "C": np.linspace(1, 0.8, 260),
        }
    )
    strat._fetch_prices = lambda: prices
    pf = DummyPF()
    await strat.build(pf)
    return pf.weights


def test_volatility_weights():
    weights = asyncio.run(_run())
    assert weights == {"B": 1.0}
