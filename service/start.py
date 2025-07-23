import uvicorn
import pandas as pd
import argparse

from service.config import (
    API_TOKEN,
    PG_URI,
    CACHE_TTL,
    API_HOST,
    API_PORT,
)
import time
from database import db_ping, init_db
import asyncio
from scrapers.universe import (
    download_sp500,
    download_sp400,
    download_russell2000,
    load_sp500,
    load_sp400,
    load_russell2000,
)
from scrapers.politician import fetch_politician_trades
from scrapers.lobbying import fetch_lobbying_data
from scrapers.wiki import fetch_trending_wiki_views
from scrapers.dc_insider import fetch_dc_insider_scores
from scrapers.gov_contracts import fetch_gov_contracts
from scrapers.app_reviews import fetch_app_reviews
from scrapers.google_trends import fetch_google_trends
from scrapers.wallstreetbets import fetch_wsb_mentions
from scrapers.analyst_ratings import fetch_analyst_ratings
from scrapers.insider_buying import fetch_insider_buying
from scrapers.news import fetch_stock_news
from scrapers.sp500_index import fetch_sp500_history
from analytics.tracking import update_all_ticker_scores
from service.logger import get_logger

log = get_logger("startup")

SCRAPERS = [
    ("politician_trades", fetch_politician_trades),
    ("lobbying", fetch_lobbying_data),
    ("wiki_views", fetch_trending_wiki_views),
    ("dc_insider_scores", fetch_dc_insider_scores),
    ("gov_contracts", fetch_gov_contracts),
    ("app_reviews", fetch_app_reviews),
    ("google_trends", fetch_google_trends),
    ("wsb_mentions", fetch_wsb_mentions),
    ("analyst_ratings", fetch_analyst_ratings),
    ("insider_buying", fetch_insider_buying),
    ("stock_news", fetch_stock_news),
    ("sp500_history", lambda: fetch_sp500_history(365)),
    ("ticker_scores", update_all_ticker_scores),
]


def wait_for_mariadb(retries: int = 5, delay: float = 2.0) -> bool:
    """Try ``db_ping`` multiple times before giving up."""
    for _ in range(retries):
        if db_ping():
            return True
        time.sleep(delay)
    return False


async def run_startup_scrapers() -> None:
    """Run all data scrapers sequentially and log progress."""
    for name, func in SCRAPERS:
        try:
            result = func()
            if asyncio.iscoroutine(result):
                data = await result
            else:
                data = result
            rows = cols = 0
            if isinstance(data, pd.DataFrame):
                rows, cols = data.shape
            elif isinstance(data, (list, tuple)):
                rows = len(data)
                if rows and isinstance(data[0], dict):
                    cols = len(data[0])
            elif isinstance(data, dict):
                rows = len(data)
                if rows:
                    cols = (
                        len(next(iter(data.values())))
                        if isinstance(next(iter(data.values())), dict)
                        else 0
                    )
            log.info(f"{name} completed: {rows}x{cols}")
        except Exception as exc:
            log.warning(f"{name} failed: {exc}")


def validate_startup() -> None:
    """Ensure config and tables exist before starting the API."""
    if not PG_URI:
        raise RuntimeError("PG_URI not set")
    if not API_TOKEN:
        raise RuntimeError("API_TOKEN not set")
    if CACHE_TTL <= 0:
        raise RuntimeError("CACHE_TTL must be positive")
    if not wait_for_mariadb():
        raise RuntimeError(f"MariaDB connection failed ({PG_URI})")
    init_db()
    download_sp500()
    download_sp400()
    download_russell2000()
    universe = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    if len(universe) < 2000:
        log.warning(f"universe size {len(universe)} < 2000")


def start_api(host: str | None = None, port: int | None = None) -> None:
    """Run startup checks, then launch the FastAPI service."""
    validate_startup()
    asyncio.run(run_startup_scrapers())
    h = host or API_HOST
    p = port or API_PORT
    uvicorn.run("service.api:app", host=h, port=p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the portfolio API")
    parser.add_argument("--host", default=None, help="Interface to bind")
    parser.add_argument("--port", type=int, default=None, help="Port number")
    args = parser.parse_args()
    start_api(args.host, args.port)
