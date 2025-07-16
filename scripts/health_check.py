from __future__ import annotations

from logger import get_logger
from database import db, pf_coll, trade_coll, metric_coll
from scrapers.universe import load_sp500, load_sp400, load_russell2000

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
    print(check_system())
