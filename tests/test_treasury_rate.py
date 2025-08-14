import os
import datetime as dt
import pandas as pd
from fastapi.testclient import TestClient

import analytics.utils as utils


def _mock_ticker(call_counter):
    class DummyTicker:
        def history(self, period="1d"):
            call_counter[0] += 1
            return pd.DataFrame({"Close": [5.0]})
    return DummyTicker


def test_treasury_rate_cache(monkeypatch):
    calls = [0]
    monkeypatch.setattr(utils.yf, "Ticker", lambda _: _mock_ticker(calls)())
    utils._TREASURY_CACHE["rate"] = 0.0
    utils._TREASURY_CACHE["timestamp"] = dt.datetime.fromtimestamp(0)

    rate1 = utils.get_treasury_rate(force=True)
    rate2 = utils.get_treasury_rate()
    assert rate1 == rate2 == 0.05
    assert calls[0] == 1

    utils._TREASURY_CACHE["timestamp"] = dt.datetime.utcnow() - dt.timedelta(days=2)
    rate3 = utils.get_treasury_rate()
    assert rate3 == 0.05
    assert calls[0] == 2


def test_refresh_route(monkeypatch):
    os.environ["API_TOKEN"] = "token"
    calls = [0]
    monkeypatch.setattr(utils.yf, "Ticker", lambda _: _mock_ticker(calls)())
    utils._TREASURY_CACHE["rate"] = 0.0
    utils._TREASURY_CACHE["timestamp"] = dt.datetime.fromtimestamp(0)
    from importlib import reload
    import service.config as config
    import service.api as api

    reload(config)
    api = reload(api)
    client = TestClient(api.app)

    resp = client.get("/refresh/treasury_rate?token=token")
    assert resp.status_code == 200
    assert resp.json()["rate"] == 0.05
    assert calls[0] == 1
