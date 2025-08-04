from fastapi.testclient import TestClient

from service.api import app
from service.config import API_TOKEN

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


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
