import pytest
from fastapi.testclient import TestClient
from service.api import app, sched

sched.start = lambda *a, **k: None
sched.stop = lambda *a, **k: None


@pytest.fixture()
def client():
    """Fresh TestClient for each test to avoid hanging threads."""
    with TestClient(app) as c:
        yield c
