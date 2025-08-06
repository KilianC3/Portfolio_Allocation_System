import pytest
from fastapi.testclient import TestClient

from service.api import app, portfolios
from service.config import API_TOKEN
from core import equity as equity_mod
from tests.test_portfolio_positions import DummyGW


class DummyColl:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)

    def find(self, q=None, projection=None):
        q = q or {}

        def match(d):
            return all(d.get(k) == v for k, v in q.items())

        return [d for d in self.docs if match(d)]

    def find_one(self, q):
        for d in self.find(q):
            return d
        return None

    def update_one(self, match, update, upsert=False):
        doc = self.find_one(match)
        if doc:
            doc.update(update.get("$set", {}))
        elif upsert:
            new_doc = match.copy()
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)


client = TestClient(app)


def _auth(path: str) -> str:
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return path + (sep + f"token={token}" if token else "")


def test_strategy_params_round_trip(monkeypatch):
    pf_coll = DummyColl()
    weight_coll = DummyColl()
    monkeypatch.setattr(equity_mod, "pf_coll", pf_coll)
    monkeypatch.setattr(equity_mod, "weight_coll", weight_coll)
    monkeypatch.setattr("service.api.pf_coll", pf_coll)

    pf = equity_mod.EquityPortfolio("test", gateway=DummyGW(), pf_id="pf1")
    portfolios[pf.id] = pf

    data = {
        "weights": {"AAPL": 0.6, "MSFT": 0.4},
        "strategy": "min_variance",
        "risk_target": 0.12,
        "allowed_strategies": ["max_sharpe", "min_variance"],
    }
    resp = client.put(_auth(f"/portfolios/{pf.id}/weights"), json=data)
    assert resp.status_code == 200

    resp = client.get(_auth("/portfolios"))
    obj = resp.json()["portfolios"][0]
    assert obj["strategy"] == "min_variance"
    assert obj["risk_target"] == 0.12
    assert obj["allowed_strategies"] == ["max_sharpe", "min_variance"]

    bad = {
        "weights": {"AAPL": 0.6, "MSFT": 0.4},
        "strategy": "risk_parity",
    }
    resp = client.put(_auth(f"/portfolios/{pf.id}/weights"), json=bad)
    assert resp.status_code == 400
