import uvicorn
import argparse
import asyncio

from service.config import (
    API_TOKEN,
    PG_URI,
    CACHE_TTL,
    API_HOST,
    API_PORT,
)
import time
from database import db_ping, init_db
from scripts.populate import run_scrapers
from service.logger import get_logger
from service.api import load_portfolios, sched

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


async def _launch_server(host: str, port: int) -> None:
    config = uvicorn.Config("service.api:app", host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def _startup_tasks() -> None:
    init_db()
    load_portfolios()
    sched.start()
    await run_scrapers()


def start_api(host: str | None = None, port: int | None = None) -> None:
    """Launch the API first, then run setup tasks in the background."""
    validate_config()

    async def runner() -> None:
        h = host or API_HOST
        p = port or API_PORT
        server_task = asyncio.create_task(_launch_server(h, p))
        await asyncio.sleep(1)
        await _startup_tasks()
        await server_task

    asyncio.run(runner())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the portfolio API")
    parser.add_argument("--host", default=None, help="Interface to bind")
    parser.add_argument("--port", type=int, default=None, help="Port number")
    args = parser.parse_args()
    start_api(args.host, args.port)
