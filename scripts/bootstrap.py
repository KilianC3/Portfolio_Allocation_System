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

    if db_ping():
        _log.info("postgres PASS")
    else:
        _log.warning("postgres FAIL")
        errs.append("postgres")

    try:
        gw = AlpacaGateway()
        await gw.account()
        await gw.close()
        _log.info("alpaca PASS")
    except Exception as exc:  # pragma: no cover - network optional
        _log.warning(f"alpaca FAIL: {exc}")
        errs.append(f"alpaca: {exc}")

    try:
        led = MasterLedger()
        await led.redis.ping()
        _log.info("ledger PASS")
    except Exception as exc:  # pragma: no cover - redis optional
        _log.warning(f"ledger FAIL: {exc}")
        errs.append(f"ledger: {exc}")

    try:
        df = pd.DataFrame({"A": [0.1, -0.1], "B": [0.05, 0.02]}, index=pd.to_datetime(["2024-01-01", "2024-01-08"]))
        compute_weights(df)
        _log.info("allocation PASS")
    except Exception as exc:  # pragma: no cover - numeric errors
        _log.warning(f"allocation FAIL: {exc}")
        errs.append(f"allocation: {exc}")

    if errs:
        _log.warning({"checklist": errs})
        raise RuntimeError("; ".join(errs))
    _log.info("system checklist complete")


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

    for name, func in scrapers:
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
                    val = next(iter(data.values()))
                    if isinstance(val, dict):
                        cols = len(val)
            _log.info(f"{name} PASS {rows}x{cols}")
        except Exception as exc:
            _log.warning(f"{name} FAIL: {exc}")


def main() -> None:
    _log.info("initialising database and running scrapers")
    init_db()
    asyncio.run(run_scrapers())
    asyncio.run(system_checklist())
    _log.info("bootstrap complete")


if __name__ == "__main__":
    main()
