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
from scrapers.volatility_momentum import fetch_volatility_momentum_summary
from scrapers.leveraged_sector_momentum import fetch_leveraged_sector_summary
from scrapers.sector_momentum import fetch_sector_momentum_summary
from scrapers.smallcap_momentum import fetch_smallcap_momentum_summary
from scrapers.upgrade_momentum import fetch_upgrade_momentum_summary
from analytics.tracking import update_all_ticker_scores

_log = get_logger("populate")


async def run_scrapers(force: bool = False) -> dict[str, tuple[int, int]]:
    """Run all scrapers sequentially and log row counts.

    Parameters
    ----------
    force: bool
        If True, bypass staleness checks and run every scraper.

    Returns
    -------
    dict
        Mapping of scraper name to a ``(rows, cols)`` tuple summarising the
        output. This allows callers to emit their own consolidated log
        messages, for example to highlight momentum scraper results during
        bootstrap.
    """
    await asyncio.to_thread(download_sp500)
    await asyncio.to_thread(download_sp400)
    await asyncio.to_thread(download_russell2000)
    sp500 = load_sp500()
    sp400 = load_sp400()
    r2k = load_russell2000()
    universe = set(sp500) | set(sp400) | set(r2k)
    if len(universe) < 2000:
        _log.warning(f"universe size {len(universe)} < 2000")

    today = pd.Timestamp.utcnow().normalize()
    results: dict[str, tuple[int, int]] = {}

    wiki_task: asyncio.Task | None = None
    if force or not has_recent_rows("wiki_views", today):
        _log.info("wiki_views start")
        if asyncio.iscoroutinefunction(fetch_trending_wiki_views):
            wiki_task = asyncio.create_task(fetch_trending_wiki_views())
        else:
            wiki_task = asyncio.create_task(asyncio.to_thread(fetch_trending_wiki_views))
    else:
        _log.info("wiki_views already current - skipping")

    scrapers = [
        ("politician_trades", fetch_politician_trades),
        ("lobbying", fetch_lobbying_data),
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
    }

    for name, func in scrapers:
        _log.info(f"{name} start")
        try:
            table = table_map.get(name, name)
            if not force:
                if name in {"ticker_scores"}:
                    if (
                        db.conn
                        and db[table].count_documents({"date": today.date()}) > 0
                    ):
                        _log.info(f"{name} already current - skipping")
                        continue
                elif (
                    name != "analyst_ratings" and has_recent_rows(table, today)
                ):
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
            if rows == 0:
                _log.warning(f"{name} produced no rows")
            else:
                _log.info(f"{name} PASS {rows}x{cols}")
            results[name] = (rows, cols)
        except Exception as exc:
            _log.exception(f"{name} FAIL: {exc}")
            results[name] = (0, 0)
    if wiki_task:
        try:
            data = await asyncio.wait_for(wiki_task, timeout=300)
            rows = len(data)
            cols = len(data[0]) if rows and isinstance(data[0], dict) else 0
            if rows == 0:
                _log.warning("wiki_views produced no rows")
            else:
                _log.info(f"wiki_views PASS {rows}x{cols}")
            results["wiki_views"] = (rows, cols)
        except asyncio.TimeoutError:
            wiki_task.cancel()
            _log.exception("wiki_views timed out")
            results["wiki_views"] = (0, 0)
        except Exception as exc:  # pragma: no cover - network optional
            _log.exception(f"wiki_views FAIL: {exc}")
            results["wiki_views"] = (0, 0)

    return results


def main(argv: list[str] | None = None) -> None:
    """Initialise the database and run all scrapers."""
    import argparse

    parser = argparse.ArgumentParser(description="Populate the database")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run all scrapers regardless of existing data",
    )
    args = parser.parse_args(argv)

    _log.info("initialising database and running scrapers")
    init_db()
    summary = asyncio.run(run_scrapers(force=args.force))
    _log.info({"scrapers": summary})
    _log.info("populate complete")


if __name__ == "__main__":
    main()
