from fastapi.testclient import TestClient
import datetime as dt
from fastapi.testclient import TestClient

from service.api import app, returns_coll, metric_coll
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_dashboard_endpoint(monkeypatch):
    returns_docs = [
        {"date": dt.date(2024, 1, 1), "return_pct": 0.01},
        {"date": dt.date(2024, 1, 2), "return_pct": -0.02},
    ]

    class DummyQuery:
        def __init__(self, docs):
            self._docs = docs

        def sort(self, field, direction):
            return self

        def limit(self, n):
            return self

        def __iter__(self):
            return iter(self._docs)

    monkeypatch.setattr(returns_coll, "find", lambda q: DummyQuery(returns_docs))
    monkeypatch.setattr(
        metric_coll,
        "find_one",
        lambda q, sort=None: {"exposures": {"Tech": 0.7}, "alpha": 0.1, "beta": 1.2},
    )

    resp = _get("/dashboard/pf1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["returns"][0]["value"] == 0.01
    assert data["exposures"]["Tech"] == 0.7
    assert data["alpha"] == 0.1
    assert data["beta"] == 1.2
