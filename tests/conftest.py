import os
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

    _orig_del = _CurlSession.__del__

    def _safe_del(self):  # type: ignore[no-untyped-def]
        try:
            _orig_del(self)
        except Exception:
            pass

    _CurlSession.__del__ = _safe_del  # type: ignore[assignment]
except Exception:  # pragma: no cover
    pass


@pytest.fixture(scope="session", autouse=True)
def _close_yf_session():
    """Ensure yfinance's global HTTP session is closed."""
    yield
    try:
        from yfinance.data import YfData

        sess = getattr(YfData(), "_session", None)
        if sess is not None:
            sess.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def client():
    """Single TestClient for all API tests."""
    with TestClient(app) as c:
        yield c
