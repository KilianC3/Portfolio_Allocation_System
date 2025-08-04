from __future__ import annotations

import datetime as dt
from typing import List

from service.logger import get_scraper_logger
from database import init_db, lev_sector_coll
from strategies.leveraged_sector import DEFAULT_TICKERS as LEVERAGED
from .momentum_common import _weekly_closes
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors

log = get_scraper_logger(__name__)
_LEV_N = 3


def fetch_leveraged_sector_summary(weeks: int = 13) -> List[dict]:
    """Store 13-week returns for leveraged sector ETFs."""
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("leveraged_sector_momentum").time():
        try:
            px = _weekly_closes(list(LEVERAGED), weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("leveraged_sector_momentum").inc()
            log.exception("leveraged batch failed: %s", exc)
            return []
        ret = px.iloc[-1] / px.iloc[-weeks] - 1
        top = ret.sort_values(ascending=False).head(_LEV_N)
        rows: List[dict] = []
        lev_sector_coll.delete_many({"date": end})
        for sym in top.index:
            item = {"symbol": sym, "date": end, "_retrieved": now}
            lev_sector_coll.update_one(
                {"symbol": sym, "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("leveraged_sector_momentum", rows)
    log.info("leveraged_sector_momentum wrote %d rows", len(rows))
    return rows
