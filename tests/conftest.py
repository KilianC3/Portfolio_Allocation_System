import os
import sys
import types
import asyncio
import contextlib
import pytest
from fastapi.testclient import TestClient
from service.api import app, sched

# Avoid starting background scheduler threads during tests
sched.start = lambda *a, **k: None
sched.stop = lambda *a, **k: None
sched.register_jobs = lambda *a, **k: None

# Force yfinance to use standard requests instead of curl_cffi
try:  # pragma: no cover - optional dependency
    import requests as _requests
    sys.modules["curl_cffi"] = types.SimpleNamespace(requests=_requests)
except Exception:
    pass


@pytest.fixture(scope="session", autouse=True)
def _close_yf_session():
    """Expose teardown hook; avoid closing to prevent curl hang."""
    yield


@pytest.fixture(scope="session", autouse=True)
def _cancel_pending_tasks():
    """Ensure leftover asyncio tasks do not block test shutdown."""
    yield
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:  # pragma: no cover - no running loop
        return
    tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
    for t in tasks:
        t.cancel()
        with contextlib.suppress(Exception):
            loop.run_until_complete(t)


@pytest.fixture()
def client():
    """Fresh TestClient for each test to avoid lingering threads."""
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    """Force interpreter exit to avoid lingering background resources."""
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr:
        tr.write_line(f"{session.testscollected} tests completed")
    os._exit(exitstatus)
