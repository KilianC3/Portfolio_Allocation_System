import pytest
import httpx

from execution.gateway import AlpacaGateway, ExecutionGateway
from ledger.master_ledger import MasterLedger
from service.api import shutdown_event, portfolios
from core.equity import EquityPortfolio


class DummyRedis:
    def __init__(self):
        self.streams = {}

    async def xadd(self, key, data):
        self.streams.setdefault(key, []).append(data)
        return "id"

    async def xrange(self, key):
        return [(str(i), d) for i, d in enumerate(self.streams.get(key, []))]

    async def xtrim(self, key, maxlen, approximate=True):
        if key in self.streams and len(self.streams[key]) > maxlen:
            self.streams[key] = self.streams[key][-maxlen:]


@pytest.mark.asyncio
async def test_order_failure_cancels_reservation(monkeypatch):
    ledger = MasterLedger()
    dummy = DummyRedis()
    monkeypatch.setattr(ledger, "redis", dummy)

    gw = AlpacaGateway()

    async def pv():
        return 1000

    async def pf_pos(symbol, pf_id):
        return 0

    async def price(symbol):
        return 100

    async def request(method, path, **kwargs):
        if path == "/v2/orders":
            raise httpx.HTTPError("boom")
        return {}

    monkeypatch.setattr(gw, "_pv", pv)
    monkeypatch.setattr(gw, "_pf_position_value", pf_pos)
    monkeypatch.setattr(gw, "_price", price)
    monkeypatch.setattr(gw, "_request", request)

    with pytest.raises(httpx.HTTPError):
        await gw.order_to_pct("AAPL", 0.1, pf_id="pf1", ledger=ledger)
    assert await ledger.free_float("pf1", "AAPL") == pytest.approx(0)
    await gw.close()


class DummyGateway(ExecutionGateway):
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True

    async def order_to_pct(self, *a, **k):
        pass

    async def submit_batch(self, orders):
        pass


@pytest.mark.asyncio
async def test_shutdown_closes_gateways():
    portfolios.clear()
    pf = EquityPortfolio("pf", gateway=DummyGateway())
    portfolios[pf.id] = pf
    await shutdown_event()
    assert pf.gateway.closed
    portfolios.clear()
