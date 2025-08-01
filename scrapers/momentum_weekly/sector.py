from __future__ import annotations

import datetime as dt
from typing import List

from service.logger import get_scraper_logger
from database import init_db, sector_mom_coll
from strategies.sector_momentum import SECTOR_ETFS
from .common import _weekly_closes
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors

log = get_scraper_logger(__name__)
_SECTOR_N = 3


def fetch_sector_momentum_summary(weeks: int = 26) -> List[dict]:
    """Store 26-week returns for S&P sector ETFs."""
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    with scrape_latency.labels("sector_momentum_weekly").time():
        try:
            px = _weekly_closes(list(SECTOR_ETFS), weeks)
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("sector_momentum_weekly").inc()
            log.exception("sector batch failed: %s", exc)
            return []
        ret = px.iloc[-1] / px.iloc[-weeks] - 1
        top = ret.sort_values(ascending=False).head(_SECTOR_N)
        rows: List[dict] = []
        sector_mom_coll.delete_many({"date": end})
        for sym in top.index:
            item = {"symbol": sym, "date": end, "_retrieved": now}
            sector_mom_coll.update_one(
                {"symbol": sym, "date": end}, {"$set": item}, upsert=True
            )
            rows.append(item)
    if rows:
        append_snapshot("sector_momentum_weekly", rows)
    log.info("sector_momentum_weekly wrote %d rows", len(rows))
    return rows
