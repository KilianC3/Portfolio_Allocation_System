import asyncio
from service.logger import get_logger
from database import init_db, db_ping
from execution.gateway import AlpacaGateway
from ledger.master_ledger import MasterLedger
from analytics.allocation_engine import compute_weights
import pandas as pd
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
from scrapers.news import fetch_stock_news
from scrapers.insider_buying import fetch_insider_buying
from scrapers.sp500_index import fetch_sp500_history
from scrapers.analyst_ratings import fetch_analyst_ratings
from analytics.tracking import update_all_ticker_scores

_log = get_logger("bootstrap")


async def system_checklist() -> None:
    """Verify connectivity to core components."""
    errs = []
    if not db_ping():
        errs.append("postgres")
    try:
        gw = AlpacaGateway()
        await gw.account()
        await gw.close()
    except Exception as exc:  # pragma: no cover - network optional
        errs.append(f"alpaca: {exc}")
    try:
        led = MasterLedger()
        await led.redis.ping()
    except Exception as exc:  # pragma: no cover - redis optional
        errs.append(f"ledger: {exc}")
    try:
        df = pd.DataFrame(
            {"A": [0.1, -0.1], "B": [0.05, 0.02]},
            index=pd.to_datetime(["2024-01-01", "2024-01-08"]),
        )
        compute_weights(df)
    except Exception as exc:  # pragma: no cover - numeric errors
        errs.append(f"allocation: {exc}")
    if errs:
        _log.warning({"checklist": errs})
        raise RuntimeError("; ".join(errs))
    _log.info("system checklist passed")


async def run_scrapers() -> None:
    # scrape universe first to ensure downstream scrapers have a full ticker list
    await asyncio.to_thread(download_sp500)
    await asyncio.to_thread(download_sp400)
    await asyncio.to_thread(download_russell2000)
    universe = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    if len(universe) < 2000:
        _log.warning(f"universe size {len(universe)} < 2000")
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
        asyncio.to_thread(update_all_ticker_scores),
    )


def main() -> None:
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(system_checklist())
    asyncio.run(run_scrapers())
    _log.info("bootstrap complete")


if __name__ == "__main__":
    main()
