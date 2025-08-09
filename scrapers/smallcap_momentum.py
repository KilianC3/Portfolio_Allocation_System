from __future__ import annotations

import datetime as dt
from typing import Iterable, List

import pandas as pd

from service.logger import get_scraper_logger
from database import init_db, smallcap_mom_coll
from .momentum_common import _CHUNK, _weekly_closes
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors

log = get_scraper_logger(__name__)
_SMALL_N = 10


def fetch_smallcap_momentum_summary(
    tickers: Iterable[str], weeks: int = 4
) -> List[dict]:
    """Store top weekly return small caps."""
    symbols = list(tickers)
    if not symbols:
        return []
    init_db()
    end = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc)
    rets: list[pd.DataFrame] = []
    with scrape_latency.labels("smallcap_momentum_weekly").time():
        for i in range(0, len(symbols), _CHUNK):
            batch = symbols[i : i + _CHUNK]
            try:
                px = _weekly_closes(batch, weeks)
            except Exception as exc:  # pragma: no cover - network optional
                scrape_errors.labels("smallcap_momentum_weekly").inc()
                log.exception("smallcap batch %s failed: %s", batch[:3], exc)
                continue
            last = px.iloc[-1]
            ret = px.iloc[-1] / px.iloc[-weeks] - 1
            df = pd.DataFrame({"price": last, "ret": ret})
            rets.append(df)
    if not rets:
        return []
    all_df = pd.concat(rets)
    top = (
        all_df.dropna(subset=["ret"]).sort_values("ret", ascending=False).head(_SMALL_N)
    )
    smallcap_mom_coll.delete_many({"date": end})
    rows: List[dict] = []
    for sym in top.index:
        item = {"symbol": sym, "date": end, "_retrieved": now}
        smallcap_mom_coll.update_one(
            {"symbol": sym, "date": end}, {"$set": item}, upsert=True
        )
        rows.append(item)
    if rows:
        append_snapshot("smallcap_momentum_weekly", rows)
    log.info("smallcap_momentum_weekly wrote %d rows", len(rows))
    return rows


if __name__ == "__main__":
    from scrapers.universe import load_russell2000

    rows = fetch_smallcap_momentum_summary(load_russell2000())
    print(f"ROWS={len(rows)}")
