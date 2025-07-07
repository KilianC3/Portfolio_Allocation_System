import os

os.environ["PG_URI"] = "postgresql://localhost/test"

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_close_position_endpoint():
    # create portfolio
    resp = client.post("/portfolios", json={"name": "demo"})
    assert resp.status_code == 200
    pf_id = resp.json()["id"]
    # set weights
    client.put(f"/portfolios/{pf_id}/weights", json={"weights": {"AAPL": 1.0}})
    # close position
    resp = client.post(f"/close/{pf_id}/AAPL")
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"
    # ensure weights removed
    res = client.get("/portfolios").json()["portfolios"]
    w = next(p["weights"] for p in res if p["id"] == pf_id)
    assert "AAPL" not in w
