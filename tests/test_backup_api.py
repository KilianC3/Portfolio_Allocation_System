from fastapi.testclient import TestClient

from service.api import app
from service.config import API_TOKEN

client = TestClient(app)


def _post(path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.post(path + (sep + f"token={token}" if token else ""))


def test_backup_and_restore_endpoints(monkeypatch):
    called = {}
    monkeypatch.setattr(
        "service.api.backup_to_github", lambda: called.setdefault("b", True)
    )
    resp = _post("/db/backup")
    assert resp.status_code == 200
    assert called.get("b")

    monkeypatch.setattr("service.api.restore_from_github", lambda: 3)
    resp = _post("/db/restore")
    assert resp.status_code == 200
    assert resp.json()["restored"] == 3
