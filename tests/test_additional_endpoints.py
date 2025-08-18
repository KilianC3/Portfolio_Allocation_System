from fastapi.testclient import TestClient
import service.api as api_module
from service.config import API_TOKEN

client = TestClient(api_module.app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


class DummyCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, field, direction):
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class DummyCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *args, **kwargs):
        return DummyCursor(list(self._docs))


def test_news_headlines_endpoint(monkeypatch):
    docs = [{"_id": 1, "headline": "h", "_retrieved": "2024-01-01"}]
    monkeypatch.setattr(api_module, "news_coll", DummyCollection(docs))
    resp = _get("/news_headlines")
    assert resp.status_code == 200
    data = resp.json()["records"]
    assert data[0]["headline"] == "h"
    assert data[0]["id"] == "1"


def test_reddit_mentions_endpoint(monkeypatch):
    docs = [{"_id": 2, "ticker": "ABC", "mentions": 5, "_retrieved": "2024-01-02"}]
    monkeypatch.setattr(api_module, "reddit_coll", DummyCollection(docs))
    resp = _get("/reddit_mentions")
    assert resp.status_code == 200
    data = resp.json()["records"]
    assert data[0]["ticker"] == "ABC"
    assert data[0]["id"] == "2"


def test_schema_version_endpoint(monkeypatch):
    class DummySchema:
        def find_one(self, sort=None):
            return {"version": 3}

    monkeypatch.setattr(api_module, "schema_coll", DummySchema())
    resp = _get("/schema_version")
    assert resp.status_code == 200
    assert resp.json()["version"] == 3


def test_weight_history_endpoint(monkeypatch):
    docs = [
        {"_id": 3, "portfolio_id": "pf1", "date": "2024-01-01", "weights": {"A": 0.5}}
    ]
    monkeypatch.setattr(api_module, "weight_coll", DummyCollection(docs))
    resp = _get("/weight_history/pf1")
    assert resp.status_code == 200
    data = resp.json()["weights"]
    assert data[0]["weights"]["A"] == 0.5
    assert data[0]["id"] == "3"
