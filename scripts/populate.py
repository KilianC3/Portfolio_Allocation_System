# Run all scrapers to populate the database.
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
from service.logger import get_logger
from infra.data_store import has_recent_rows
from database import init_db, db
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
from scrapers import full_fundamentals
from scrapers.momentum_weekly.volatility import fetch_volatility_momentum_summary
from scrapers.momentum_weekly.leveraged_sector import fetch_leveraged_sector_summary
from scrapers.momentum_weekly.sector import fetch_sector_momentum_summary
from scrapers.momentum_weekly.smallcap import fetch_smallcap_momentum_summary
from scrapers.momentum_weekly.upgrade import fetch_upgrade_momentum_summary
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
        ("volatility_momentum", fetch_volatility_momentum_summary),
        ("leveraged_sector_momentum", fetch_leveraged_sector_summary),
        ("sector_momentum_weekly", fetch_sector_momentum_summary),
        (
            "smallcap_momentum_weekly",
            lambda: fetch_smallcap_momentum_summary(load_russell2000()),
        ),
        (
            "upgrade_momentum_weekly",
            lambda: fetch_upgrade_momentum_summary(universe),
        ),
        ("full_fundamentals", lambda: full_fundamentals.main(universe)),
        ("analyst_ratings", fetch_analyst_ratings),
        ("insider_buying", fetch_insider_buying),
        ("stock_news", fetch_stock_news),
        ("sp500_history", lambda: fetch_sp500_history(365)),
        ("ticker_scores", update_all_ticker_scores),
    ]

    table_map = {
        "sp500_history": "sp500_index",
        "ticker_scores": "ticker_scores",
        "wsb_mentions": "reddit_mentions",
        "stock_news": "news_headlines",
        "volatility_momentum": "volatility_momentum",
        "leveraged_sector_momentum": "leveraged_sector_momentum",
        "sector_momentum_weekly": "sector_momentum_weekly",
        "smallcap_momentum_weekly": "smallcap_momentum_weekly",
        "upgrade_momentum_weekly": "upgrade_momentum_weekly",
        "full_fundamentals": "top_scores",
    }

    today = pd.Timestamp.utcnow().normalize()

    for name, func in scrapers:
        _log.info(f"{name} start")
        try:
            table = table_map.get(name, name)
            if name in {"ticker_scores", "full_fundamentals"}:
                if db.conn and db[table].count_documents({"date": today.date()}) > 0:
                    _log.info(f"{name} already current - skipping")
                    continue
            elif has_recent_rows(table, today):
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
            _log.exception(f"{name} FAIL: {exc}")


def main() -> None:
    """Initialise the database and run all scrapers."""
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(run_scrapers())
    _log.info("populate complete")


if __name__ == "__main__":
    main()
