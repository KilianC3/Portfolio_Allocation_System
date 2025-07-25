import argparse
import asyncio
import time

import pandas as pd
import uvicorn

from service.config import (
    API_TOKEN,
    PG_URI,
    CACHE_TTL,
    API_HOST,
    API_PORT,
)
from database import db_ping, init_db
from service.logger import get_logger
from service.api import load_portfolios, sched
from scripts.populate import run_scrapers
from execution.gateway import AlpacaGateway
from ledger.master_ledger import MasterLedger
from analytics.allocation_engine import compute_weights

log = get_logger("startup")


def wait_for_mariadb(retries: int = 5, delay: float = 2.0) -> bool:
    """Try ``db_ping`` multiple times before giving up."""
    for _ in range(retries):
        if db_ping():
            return True
        time.sleep(delay)
    return False


def validate_config() -> None:
    """Check core settings and database connectivity."""
    if not PG_URI:
        raise RuntimeError("PG_URI not set")
    if not API_TOKEN:
        raise RuntimeError("API_TOKEN not set")
    if CACHE_TTL <= 0:
        raise RuntimeError("CACHE_TTL must be positive")
    if not wait_for_mariadb():
        raise RuntimeError(f"MariaDB connection failed ({PG_URI})")


async def system_checklist() -> None:
    """Verify connectivity to all core components."""
    errs: list[str] = []

    if db_ping():
        log.info("mariadb PASS")
    else:
        log.warning("mariadb FAIL")
        errs.append("mariadb")

    try:
        gw = AlpacaGateway()
        await gw.account()
        await gw.close()
        log.info("alpaca PASS")
    except Exception as exc:  # pragma: no cover - network optional
        log.warning(f"alpaca FAIL: {exc}")
        errs.append(f"alpaca: {exc}")

    try:
        led = MasterLedger()
        await led.redis.ping()
        log.info("ledger PASS")
    except Exception as exc:  # pragma: no cover - redis optional
        log.warning(f"ledger FAIL: {exc}")
        errs.append(f"ledger: {exc}")

    try:
        df = pd.DataFrame(
            {"A": [0.1, -0.1], "B": [0.05, 0.02]},
            index=pd.to_datetime(["2024-01-01", "2024-01-08"]),
        )
        compute_weights(df)
        log.info("allocation PASS")
    except Exception as exc:  # pragma: no cover - numeric errors
        log.warning(f"allocation FAIL: {exc}")
        errs.append(f"allocation: {exc}")

    if errs:
        log.warning({"checklist": errs})
        raise RuntimeError("; ".join(errs))
    log.info("system checklist complete")


async def _launch_server(host: str, port: int) -> None:
    config = uvicorn.Config("service.api:app", host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def main(host: str | None = None, port: int | None = None) -> None:
    """Run setup tasks, scrapers and then launch the API."""
    log.info("startup sequence begin")
    try:
        log.info("validate config")
        validate_config()
        log.info("connectivity checks")
        await system_checklist()
        log.info("initialising database")
        init_db()
        log.info("loading portfolios")
        load_portfolios()
        log.info("starting scheduler")
        sched.start()
        log.info("running scrapers")
        await run_scrapers()
    except Exception as exc:  # pragma: no cover - startup errors
        log.exception(f"fatal startup error: {exc}")
        return
    log.info("startup complete - launching API")

    h = host or API_HOST or "192.168.0.59"
    p = port or API_PORT or 8001
    await _launch_server(h, p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the portfolio API")
    parser.add_argument("--host", default="192.168.0.59", help="Interface to bind")
    parser.add_argument("--port", type=int, default=8001, help="Port number")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
