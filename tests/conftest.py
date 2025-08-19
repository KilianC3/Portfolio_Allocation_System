import os
import asyncio
import pytest
from fastapi.testclient import TestClient
from service.api import app, sched

# Avoid starting background scheduler threads during tests
sched.start = lambda *a, **k: None
sched.stop = lambda *a, **k: None
sched.register_jobs = lambda *a, **k: None

# Patch curl_cffi Session destructor to swallow shutdown errors
try:  # pragma: no cover - optional dependency
    from curl_cffi.requests.session import Session as _CurlSession

    # Replace destructor entirely to avoid libcurl unraisable warnings
    # that can prevent pytest from terminating.
    def _safe_del(self):  # type: ignore[no-untyped-def]
        pass

    _CurlSession.__del__ = _safe_del  # type: ignore[assignment]
except Exception:  # pragma: no cover
    pass


@pytest.fixture(scope="session", autouse=True)
def _close_yf_session():
    """Expose teardown hook; avoid closing to prevent curl hang."""
    yield


@pytest.fixture()
def client():
    """Fresh TestClient for each test to avoid lingering threads."""
    with TestClient(app) as c:
        yield c
