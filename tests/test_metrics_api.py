import datetime as dt

from service.api import metric_coll
from service.config import API_TOKEN


def _get(client, path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_metrics_include_win_rate_and_vol(client, monkeypatch):
    docs = [
        {
            "date": dt.date(2024, 1, 1),
            "ret": 0.01,
            "exposure": 0.5,
            "win_rate": 0.6,
            "annual_vol": 0.2,
            "ff_expected_return": 0.05,
            "beta_smb": 0.1,
            "beta_hml": -0.2,
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

    resp = _get(client, "/metrics/testpf")
    assert resp.status_code == 200
    data = resp.json()["metrics"]
    assert data[0]["win_rate"] == 0.6
    assert data[0]["volatility"] == 0.2
    assert data[0]["ff_expected_return"] == 0.05
    assert data[0]["beta_smb"] == 0.1
    assert data[0]["beta_hml"] == -0.2
    assert data[0]["exposure"] == 0.5
    assert data[0]["ret"] == 0.01
