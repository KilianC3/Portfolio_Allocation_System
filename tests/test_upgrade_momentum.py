import asyncio
import pandas as pd
from strategies.upgrade_momentum import UpgradeMomentumStrategy


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


async def fake_rank(self, *args, **kwargs):
    data = pd.DataFrame({
        "symbol": [f"S{i}" for i in range(10)],
        "upgrades": list(range(10)),
        "downgrades": [0]*10,
        "total": [1]*10,
    })
    data["ratio"] = data["upgrades"] / data["total"]
    return data.sort_values("ratio", ascending=False)


def test_smoothing():
    strat = UpgradeMomentumStrategy([f"S{i}" for i in range(10)])
    strat._rank = fake_rank.__get__(strat)
    pf = DummyPF()
    asyncio.run(strat.build(pf))
    w1 = pf.weights.copy()
    assert abs(sum(w1.values()) - 1) < 1e-6
    asyncio.run(strat.build(pf))
    w2 = pf.weights.copy()
    assert w1 == w2
    assert len(strat.history) == 2
