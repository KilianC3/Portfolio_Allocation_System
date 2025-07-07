import asyncio
import datetime as dt

from strategies.biotech_event import BiotechBinaryEventBasket


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


async def _run():
    events = {"ABC": dt.date.today() + dt.timedelta(days=30)}
    strat = BiotechBinaryEventBasket(events)
    strat._latest_price = lambda s: 10.0
    pf = DummyPF()
    await strat.build(pf)
    return pf.weights


def test_event_weights():
    weights = asyncio.run(_run())
    assert weights == {"ABC": 1.0}
