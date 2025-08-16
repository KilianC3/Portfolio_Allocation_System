import types

from scrapers import edgar


class DummyResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_edgar_facts_success(monkeypatch):
    def fake_get(url, timeout=10):
        if "ticker" in url:
            return DummyResp(200, {"cik_str": "1234"})
        return DummyResp(
            200,
            {
                "facts": {
                    "CashAndCashEquivalentsAtCarryingValue": {
                        "units": {"USD": [{"val": 1000}]}
                    },
                    "CommonStockSharesOutstanding": {
                        "units": {"shares": [{"val": 50}]}
                    },
                    "Debt": {"units": {"USD": [{"val": 25}]}}
                }
            },
        )

    monkeypatch.setattr(edgar, "session", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(edgar, "time", types.SimpleNamespace(sleep=lambda *_: None))
    data = edgar.fetch_edgar_facts("AAPL")
    assert data["totalCash"] == 1000
    assert data["sharesOutstanding"] == 50
    assert data["totalDebt"] == 25


def test_fetch_edgar_facts_failure(monkeypatch):
    def fake_get(url, timeout=10):
        return DummyResp(404, {})

    monkeypatch.setattr(edgar, "session", types.SimpleNamespace(get=fake_get))
    monkeypatch.setattr(edgar, "time", types.SimpleNamespace(sleep=lambda *_: None))
    assert edgar.fetch_edgar_facts("MSFT") == {}
