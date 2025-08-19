import datetime as dt
from fastapi.testclient import TestClient

from service import api


class DummyJobs:
    def __init__(self):
        self.store = {}

    def find(self, q=None):
        return list(self.store.values())

    def find_one(self, q):
        return self.store.get(q.get("id"))

    def update_one(self, match, doc, upsert=False):
        item = self.store.get(match["id"], {})
        item.update(doc.get("$set", {}))
        item["id"] = match["id"]
        self.store[match["id"]] = item


def test_jobs_endpoints(monkeypatch):
    dummy = DummyJobs()
    dummy.update_one(
        {"id": "metrics"},
        {
            "$set": {
                "last_run": dt.datetime(2024, 1, 1),
                "next_run": dt.datetime(2024, 1, 2),
            }
        },
        upsert=True,
    )
    monkeypatch.setattr(api, "jobs_coll", dummy, raising=False)
    monkeypatch.setattr(api, "API_TOKEN", "token", raising=False)
    with TestClient(api.app) as client:
        res = client.get("/jobs?token=token")
        assert res.status_code == 200
        data = res.json()["jobs"]
        assert any(j["id"] == "metrics" for j in data)
        res = client.get("/jobs/metrics?token=token")
        assert res.status_code == 200
        assert res.json()["id"] == "metrics"
        monkeypatch.setattr(
            api.sched.scheduler, "modify_job", lambda job_id, next_run_time=None: None
        )
        res = client.post("/jobs/metrics/run?token=token")
        assert res.status_code == 200
        assert res.json()["status"] == "triggered"
