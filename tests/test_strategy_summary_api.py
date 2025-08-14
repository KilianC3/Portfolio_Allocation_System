from fastapi.testclient import TestClient
import datetime as dt

from service.api import app, pf_coll, metric_coll, risk_stats_coll
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_strategy_summary_aggregates(monkeypatch):
    portfolios = [{"_id": "pf1", "name": "P1", "weights": {"AAPL": 0.5}}]

    monkeypatch.setattr(pf_coll, "find", lambda *a, **k: portfolios)

    def fake_metric(q, sort=None):
        return {"date": dt.date(2024, 1, 1), "ret": 0.1, "portfolio_id": q["portfolio_id"]}

    def fake_risk(q, sort=None):
        return {"date": dt.date(2024, 1, 1), "var95": 0.05, "strategy": q["strategy"]}

    monkeypatch.setattr(metric_coll, "find_one", fake_metric)
    monkeypatch.setattr(risk_stats_coll, "find_one", fake_risk)

    resp = _get("/strategies/summary")
    assert resp.status_code == 200
    data = resp.json()["strategies"][0]
    assert data["metrics"]["ret"] == 0.1
    assert data["risk"]["var95"] == 0.05
    assert data["weights"] == {"AAPL": 0.5}
