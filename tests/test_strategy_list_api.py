from fastapi.testclient import TestClient

from service.api import app
from service.config import API_TOKEN
import strategies

client = TestClient(app)


def _get(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_strategy_list_includes_package():
    resp = _get("/strategies")
    assert resp.status_code == 200
    data = resp.json()["strategies"]
    for name in strategies.__all__:
        assert name in data
