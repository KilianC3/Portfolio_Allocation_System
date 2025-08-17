import argparse
import asyncio
import time

import pandas as pd
import uvicorn
import httpx

from service.config import (
    API_TOKEN,
    DB_URI,
    CACHE_TTL,
    API_HOST,
    API_PORT,
    ALLOC_METHOD,
)
from database import db_ping, init_db
from service.logger import get_logger
from service.api import load_portfolios
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
    if not DB_URI:
        raise RuntimeError("DB_URI not set")
    if not API_TOKEN:
        raise RuntimeError("API_TOKEN not set")
    if CACHE_TTL <= 0:
        raise RuntimeError("CACHE_TTL must be positive")
    if not wait_for_mariadb():
        raise RuntimeError(f"MariaDB connection failed ({DB_URI})")


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
        compute_weights(df, method=ALLOC_METHOD)
        log.info("allocation PASS")
    except Exception as exc:  # pragma: no cover - numeric errors
        log.warning(f"allocation FAIL: {exc}")
        errs.append(f"allocation: {exc}")

    if errs:
        log.warning({"checklist": errs})
        raise RuntimeError("; ".join(errs))
    log.info("system checklist complete")


async def _launch_server(host: str, port: int) -> asyncio.Task:
    """Start the FastAPI server and return the serving task."""
    config = uvicorn.Config("service.api:app", host=host, port=port)
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.1)
    log.info(f"api server initialised on http://{host}:{port}")
    return task


async def main(host: str | None = None, port: int | None = None) -> None:
    """Run startup tasks and then launch the API server."""
    log.info("startup sequence begin")

    h = host or API_HOST or "0.0.0.0"
    p = port or API_PORT or 8001

    log.info("validate config")
    validate_config()
    log.info("connectivity checks")
    await system_checklist()
    log.info("initialising database")
    init_db()
    log.info("loading portfolios")
    load_portfolios()
    # Scheduler is started during FastAPI's startup event
    log.info("launching api server")
    server_task = await _launch_server(h, p)
    log.info("testing api connection")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{h}:{p}/health", timeout=10)
            resp.raise_for_status()
        log.info("api connection PASS")
    except Exception as exc:  # pragma: no cover - network optional
        log.warning(f"api connection FAIL: {exc}")
        raise
    async def _run_scrapers_bg() -> None:
        try:
            log.info("running scrapers")
            results = await run_scrapers(force=True)
            log.info({"scrapers": results})
        except Exception:
            log.exception("scrapers failed")

    scraper_task = asyncio.create_task(_run_scrapers_bg())
    log.info("bootstrap complete")
    await asyncio.gather(server_task, scraper_task)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the portfolio API")
    parser.add_argument("--host", help="Interface to bind")
    parser.add_argument("--port", type=int, help="Port number")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
