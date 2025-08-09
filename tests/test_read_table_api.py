from fastapi.testclient import TestClient

from service import api as api_module
from service.api import app
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def _delete(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.delete(path + (sep + f"token={token}" if token else ""))


class DummyCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, field, direction):
        self.docs.sort(key=lambda d: d.get(field), reverse=direction == -1)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def offset(self, n):
        self.docs = self.docs[n:]
        return self

    def __iter__(self):
        return iter(self.docs)


class DummyCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query, projection=None):
        docs = [
            {k: v for k, v in d.items() if projection is None or k in projection}
            for d in self._docs
        ]
        return DummyCursor(docs)


def test_read_table_sort_and_fields(monkeypatch):
    docs = [{"_id": 1, "a": 2, "b": 3}, {"_id": 2, "a": 1, "b": 4}]
    monkeypatch.setattr(api_module, "db", {"test": DummyCollection(docs)})
    monkeypatch.setattr(api_module, "db_ping", lambda: None)

    resp = _get("/db/test?sort_by=a&order=desc&fields=a")
    assert resp.status_code == 200
    data = resp.json()["records"]
    assert data[0]["a"] == 2
    assert "b" not in data[0]
    assert "id" in data[0]


def test_read_table_invalid_order(monkeypatch):
    monkeypatch.setattr(api_module, "db", {"test": DummyCollection([])})
    monkeypatch.setattr(api_module, "db_ping", lambda: None)

    resp = _get("/db/test?order=sideways")
    assert resp.status_code == 400


class DummyShowCursor:
    def __init__(self, tables):
        self.tables = tables

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        pass

    def fetchall(self):
        return [{"Tables_in_test": t} for t in self.tables]


class DummyConn:
    def __init__(self, tables):
        self._tables = tables

    def cursor(self):
        return DummyShowCursor(self._tables)


def test_list_tables_includes_system_logs(monkeypatch):
    dummy_db = type("D", (), {"conn": DummyConn(["alpha", "beta"])} )
    monkeypatch.setattr(api_module, "db", dummy_db)
    monkeypatch.setattr(api_module, "db_ping", lambda: None)

    resp = _get("/db")
    assert resp.status_code == 200
    tables = resp.json()["tables"]
    assert "system_logs" in tables


def test_clear_db_logs(monkeypatch):
    monkeypatch.setattr(api_module, "clear_system_logs", lambda days: 7)
    resp = _delete("/db/system_logs")
    assert resp.status_code == 200
    assert resp.json()["removed"] == 7
