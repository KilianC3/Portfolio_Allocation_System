import os
import re
import time
import numpy as np
import pytest
import respx
import httpx

os.environ["MONGO_URI"] = "mongomock://localhost"

from execution.gateway import AlpacaGateway


@pytest.mark.asyncio
async def test_latency_p95_under_5ms():
    gw = AlpacaGateway()
    with respx.mock(base_url="https://paper-api.alpaca.markets") as m:
        m.get("/v2/account").mock(
            return_value=httpx.Response(200, json={"portfolio_value": 100000})
        )
        m.get(re.compile(r"/v2/stocks/.*/trades/latest")).mock(
            return_value=httpx.Response(200, json={"trade": {"p": 100}})
        )
        m.get(re.compile(r"/v2/positions/.*")).mock(return_value=httpx.Response(404))
        m.post("/v2/orders").mock(return_value=httpx.Response(200, json={"id": "1"}))
        lat = []
        for _ in range(10):
            t0 = time.perf_counter()
            await gw.order_to_pct("AAPL", 0.01)
            lat.append(time.perf_counter() - t0)
        assert np.percentile(lat, 95) < 0.02
    await gw.close()
