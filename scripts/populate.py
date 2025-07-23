# Run all scrapers to populate the database.
import asyncio
import pandas as pd
from service.logger import get_logger
from infra.data_store import has_recent_rows
from database import init_db
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

_log = get_logger("populate")


async def run_scrapers() -> None:
    """Run all scrapers sequentially and log row counts."""
    await asyncio.to_thread(download_sp500)
    await asyncio.to_thread(download_sp400)
    await asyncio.to_thread(download_russell2000)
    universe = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    if len(universe) < 2000:
        _log.warning(f"universe size {len(universe)} < 2000")

    scrapers = [
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

    table_map = {
        "sp500_history": "sp500_index",
        "ticker_scores": "ticker_scores",
    }

    today = pd.Timestamp.utcnow().normalize()

    for name, func in scrapers:
        try:
            table = table_map.get(name, name)
            if has_recent_rows(table, today):
                _log.info(f"{name} already current - skipping")
                continue
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
                    val = next(iter(data.values()))
                    if isinstance(val, dict):
                        cols = len(val)
            _log.info(f"{name} PASS {rows}x{cols}")
        except Exception as exc:
            _log.warning(f"{name} FAIL: {exc}")


def main() -> None:
    """Initialise the database and run all scrapers."""
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(run_scrapers())
    _log.info("populate complete")


if __name__ == "__main__":
    main()
