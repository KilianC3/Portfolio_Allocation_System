import os

os.environ["MONGO_URI"] = "mongomock://localhost"

from fastapi.testclient import TestClient
from api import app, sched

client = TestClient(app)


def test_schedule_reddit_strategy():
    resp = client.post(
        "/scheduler/jobs",
        json={
            "pf_id": "wsb",
            "name": "Reddit Buzz",
            "module": "strategies.wallstreetbets",
            "cls": "RedditBuzzStrategy",
            "cron_key": "weekly",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "scheduled"
    jobs = client.get("/scheduler/jobs").json()["jobs"]
    assert any(j["id"] == "wsb" for j in jobs)
