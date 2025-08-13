from __future__ import annotations

import datetime as dt
import math
from typing import Iterable, List

from service.logger import get_scraper_logger
from database import init_db, upgrade_mom_coll
from scrapers.analyst_ratings import fetch_changes
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors

log = get_scraper_logger(__name__)
_UPGRADE_N = 15


async def fetch_upgrade_momentum_summary(
    universe: Iterable[str],
    weeks: int = 4,
    top_n: int = _UPGRADE_N,
    max_symbols: int | None = None,
) -> List[dict]:
    """Store analyst upgrade momentum ratios for ``universe``.

    Parameters
    ----------
    universe:
        Iterable of tickers to evaluate.
    weeks:
        Lookback window for analyst rating changes.
    top_n:
        Number of rows returned.
    max_symbols:
        Optional cap on how many symbols are queried.  Limiting the universe
        keeps calls to the QuiverQuant API small during tests.
    """
    symbols = list(universe)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    if not symbols:
        return []
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("upgrade_momentum_weekly").time():
        try:
            df = await fetch_changes(symbols, weeks=weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("upgrade_momentum_weekly").inc()
            log.exception("upgrade fetch failed: %s", exc)
            return []
        if df.empty:
            log.warning("upgrade momentum returned no data")
            return []
        df["ratio"] = (df["upgrades"] - df["downgrades"]) / df["total"].replace(
            0, math.nan
        )
        df = df.dropna(subset=["ratio"]).sort_values("ratio", ascending=False)
        top = df.head(top_n)
        rows: List[dict] = []
        upgrade_mom_coll.delete_many({"date": end})
        for _, row in top.iterrows():
            item = {"symbol": row["symbol"], "date": end, "_retrieved": now}
            upgrade_mom_coll.update_one(
                {"symbol": item["symbol"], "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("upgrade_momentum_weekly", rows)
    log.info("upgrade_momentum_weekly wrote %d rows", len(rows))
    return rows


if __name__ == "__main__":
    import asyncio
    from scrapers.universe import load_sp500, load_sp400, load_russell2000

    universe = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    rows = asyncio.run(
        fetch_upgrade_momentum_summary(universe, top_n=5, max_symbols=100)
    )
    print(f"ROWS={len(rows)}")
