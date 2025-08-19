import pytest
from fastapi.testclient import TestClient
from service.api import app, sched

sched.start = lambda *a, **k: None
sched.stop = lambda *a, **k: None


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
