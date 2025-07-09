import asyncio
from logger import get_logger
from database import init_db
from scrapers import (
    fetch_politician_trades,
    fetch_lobbying_data,
    fetch_wiki_views,
    fetch_dc_insider_scores,
    fetch_gov_contracts,
    fetch_app_reviews,
    fetch_google_trends,
    fetch_insider_buying,
    fetch_sp500_history,
)

_log = get_logger("bootstrap")


async def run_scrapers() -> None:
    await asyncio.gather(
        fetch_politician_trades(),
        fetch_lobbying_data(),
        fetch_wiki_views(),
        fetch_dc_insider_scores(),
        fetch_gov_contracts(),
        fetch_app_reviews(),
        fetch_google_trends(),
        fetch_insider_buying(),
        asyncio.to_thread(fetch_sp500_history, 30),
    )


def main() -> None:
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(run_scrapers())
    _log.info("bootstrap complete")


if __name__ == "__main__":
    main()
