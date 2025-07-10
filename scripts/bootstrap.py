import asyncio
from logger import get_logger
from database import init_db
from scrapers.politician import fetch_politician_trades
from scrapers.lobbying import fetch_lobbying_data
from scrapers.wiki import fetch_trending_wiki_views
from scrapers.dc_insider import fetch_dc_insider_scores
from scrapers.gov_contracts import fetch_gov_contracts
from scrapers.app_reviews import fetch_app_reviews
from scrapers.google_trends import fetch_google_trends
from scrapers.wallstreetbets import fetch_wsb_mentions
from scrapers.news import fetch_stock_news
from scrapers.insider_buying import fetch_insider_buying
from scrapers.sp500_index import fetch_sp500_history
from scrapers.analyst_ratings import fetch_analyst_ratings
from analytics.tracking import update_all_ticker_returns

_log = get_logger("bootstrap")


async def run_scrapers() -> None:
    await asyncio.gather(
        fetch_politician_trades(),
        fetch_lobbying_data(),
        fetch_trending_wiki_views(),
        fetch_dc_insider_scores(),
        fetch_gov_contracts(),
        fetch_app_reviews(),
        fetch_google_trends(),
        fetch_wsb_mentions(),
        fetch_analyst_ratings(["AAPL", "MSFT"]),
        fetch_insider_buying(),
        fetch_stock_news(),
        asyncio.to_thread(fetch_sp500_history, 365),
        asyncio.to_thread(update_all_ticker_returns),
    )


def main() -> None:
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(run_scrapers())
    _log.info("bootstrap complete")


if __name__ == "__main__":
    main()
