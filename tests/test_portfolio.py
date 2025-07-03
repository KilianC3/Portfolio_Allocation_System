import os
from types import SimpleNamespace

import pytest

os.environ['MONGO_URI'] = 'mongomock://localhost'

from execution_gateway import ExecutionGateway
from core.equity import EquityPortfolio


class DummyGateway(ExecutionGateway):
    def __init__(self):
        self.last = None

    def order_to_pct(self, symbol: str, pct: float, pf_id: str | None = None):
        qty = pct * 10
        side = 'buy' if qty > 0 else 'sell'
        self.last = (symbol, qty)
        return SimpleNamespace(symbol=symbol, side=side, qty=abs(qty), filled_avg_price=1.0)


def test_positions():
    gw = DummyGateway()
    pf = EquityPortfolio('Test', gateway=gw)
    pf.set_weights({'AAPL': 1.0})
    pf.rebalance()
    pos = pf.positions()
    assert pos['AAPL'] == gw.last[1]
