import asyncio
import httpx
import respx
import pytest

from analytics.account import record_account
from execution.gateway import AlpacaGateway


@pytest.mark.asyncio
@respx.mock
async def test_record_account():
    route = respx.get("https://paper-api.alpaca.markets/v2/account").mock(
        return_value=httpx.Response(200, json={"equity": "1000", "last_equity": "900"})
    )
    gw = AlpacaGateway()
    doc = await record_account(gw)
    await gw.close()
    assert route.called
    assert doc["equity"] == 1000.0
    assert doc["paper"] is True
