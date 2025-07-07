import os
import datetime as dt

os.environ["PG_URI"] = "postgresql://localhost/test"
os.environ["API_TOKEN"] = "secret"

from fastapi.testclient import TestClient
from api import app, metric_coll

client = TestClient(app)
HEADERS = {"Authorization": "Bearer secret"}


def test_var_and_correlations():
    metric_coll.delete_many({})
    metric_coll.insert_many(
        [
            {"portfolio_id": "a", "date": dt.date(2024, 1, 1), "ret": 0.01},
            {"portfolio_id": "a", "date": dt.date(2024, 1, 2), "ret": -0.02},
            {"portfolio_id": "b", "date": dt.date(2024, 1, 1), "ret": 0.02},
            {"portfolio_id": "b", "date": dt.date(2024, 1, 2), "ret": -0.01},
        ]
    )
    r = client.get("/var", headers=HEADERS)
    assert r.status_code == 200
    assert "var" in r.json()

    r = client.get("/correlations", headers=HEADERS)
    assert r.status_code == 200
    assert "correlations" in r.json()


def test_auth_required():
    resp = client.get("/portfolios")
    assert resp.status_code == 401
