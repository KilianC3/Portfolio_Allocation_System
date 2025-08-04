from fastapi.testclient import TestClient
import datetime as dt

from service.api import app, metric_coll
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_metrics_include_win_rate_and_vol(monkeypatch):
    docs = [
        {
            "date": dt.date(2024, 1, 1),
            "ret": 0.01,
            "win_rate": 0.6,
            "annual_vol": 0.2,
            "capm_expected_return": 0.05,
        }
    ]

    class DummyQuery:
        def __init__(self, docs):
            self._docs = docs

        def sort(self, field, direction):
            return self

        def __iter__(self):
            return iter(self._docs)

    monkeypatch.setattr(metric_coll, "find", lambda q: DummyQuery(docs))

    resp = _get("/metrics/testpf")
    assert resp.status_code == 200
    data = resp.json()["metrics"]
    assert data[0]["win_rate"] == 0.6
    assert data[0]["volatility"] == 0.2
    assert data[0]["capm_expected_return"] == 0.05
