from fastapi.testclient import TestClient

from service.api import app
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def _post(path: str, json: dict):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.post(path + (sep + f"token={token}" if token else ""), json=json)


def test_risk_overview_keys():
    resp = _get("/risk/overview?strategy=dummy")
    assert resp.status_code == 200
    data = resp.json()
    for key in ["var95", "vol30d", "maxDrawdown", "beta30d", "alerts"]:
        assert key in data


def test_risk_rules_list():
    resp = _get("/risk/rules")
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_risk_rule_validation():
    bad_metric = {
        "name": "x",
        "strategy": "s",
        "metric": "bogus",
        "operator": ">",
        "threshold": 1,
    }
    resp = _post("/risk/rules", bad_metric)
    assert resp.status_code == 400
    bad_op = {**bad_metric, "metric": "var95", "operator": "??"}
    resp2 = _post("/risk/rules", bad_op)
    assert resp2.status_code == 400
