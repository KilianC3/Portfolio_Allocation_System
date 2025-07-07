import os
import pytest
from types import SimpleNamespace

os.environ["PG_URI"] = "postgresql://localhost/test"

from execution.gateway import AlpacaGateway
from core.equity import EquityPortfolio


class DummyGateway(AlpacaGateway):
    async def _price(self, symbol: str) -> float:  # override
        return 0.4

    async def _pv(self) -> float:
        return 1000

    async def _pf_position_value(self, symbol: str, pf_id: str) -> float:
        return 0

    async def _request(self, method: str, path: str, **kwargs):
        return {}


@pytest.mark.asyncio
async def test_price_guard_low_price():
    gw = DummyGateway()
    pf = EquityPortfolio("low", gateway=gw)
    pf.set_weights({"XYZ": 1.0})
    with pytest.raises(ValueError):
        await pf.rebalance()
