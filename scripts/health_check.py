from __future__ import annotations

from service.logger import get_logger
from database import db, pf_coll, trade_coll, metric_coll
from scrapers.universe import load_sp500, load_sp400, load_russell2000
import requests
import sys

_log = get_logger("health")


def check_system() -> dict:
    """Return a status dictionary and log the result."""
    status: dict[str, object] = {"metrics_frequency": "daily"}
    try:
        db.client.command("ping")
        status["database"] = "ok"
    except Exception as exc:  # pragma: no cover - connection may fail
        status["database"] = f"error: {exc}"  # pragma: no cover

    try:
        status["portfolios"] = len(list(pf_coll.find()))
        status["trades"] = len(list(trade_coll.find()))
        status["metrics"] = len(list(metric_coll.find()))
        status["tracked_universe"] = len(
            set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
        )
    except Exception as exc:  # pragma: no cover - table may be missing
        status["error"] = str(exc)

    _log.info(status)
    return status


if __name__ == "__main__":
    try:
        resp = requests.get("http://192.168.0.59:8001/readyz", timeout=5)
        resp.raise_for_status()
        print(resp.json())
    except Exception as exc:  # pragma: no cover - network optional
        _log.error(f"health check failed: {exc}")
        sys.exit(1)
    sys.exit(0)
