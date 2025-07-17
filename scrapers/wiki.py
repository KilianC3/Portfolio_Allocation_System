import datetime as dt
import json
from typing import List

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, wiki_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

log = get_logger(__name__)
from strategies.wiki_attention import (
    trending_candidates,
    wiki_title,
    cached_views,
    z_score,
)

wiki_collection = wiki_coll if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_wiki_views(page: str = "Apple_Inc", days: int = 7) -> List[dict]:
    """Fetch Wikipedia page views via the Wikimedia API."""

    log.info(f"fetch_wiki_views start page={page}")
    init_db()

    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days - 1)
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/all-agents/{page}/daily/"
        f"{start:%Y%m%d}/{end:%Y%m%d}"
    )
    with scrape_latency.labels("wiki_views").time():
        try:
            async with rate:
                text = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("wiki_views").inc()
            log.warning(f"fetch_wiki_views failed: {exc}")
            raise
    items = json.loads(text).get("items", [])
    now = dt.datetime.now(dt.timezone.utc)
    data: List[dict] = []
    for row in items:
        date = row["timestamp"][:8]
        item = {
            "page": page,
            "views": row["views"],
            "date": date,
            "_retrieved": now,
        }
        data.append(item)
        wiki_collection.update_one(
            {"page": page, "date": date},
            {"$set": item},
            upsert=True,
        )
    append_snapshot("wiki_views", data)
    log.info(f"fetched {len(data)} wiki view rows for {page}")
    return data


async def fetch_trending_wiki_views(top_k: int = 10, days: int = 7) -> List[dict]:
    """Collect page views for top trending tickers by z-score."""
    # use a zero threshold so we gather enough candidates and always
    # return ``top_k`` tickers even when yesterday's traffic was low
    log.info("fetch_trending_wiki_views start")
    cand = trending_candidates(min_views=0)
    scores = []
    for sym, name in cand.items():
        page = wiki_title(name)
        if not page:
            continue
        series = cached_views(page)
        if len(series) < 30:
            continue
        scores.append((z_score(series), page))

    top = [p for _s, p in sorted(scores, key=lambda x: x[0], reverse=True)[:top_k]]
    out: List[dict] = []
    for pg in top:
        out.extend(await fetch_wiki_views(pg, days))
    log.info(f"fetched {len(out)} trending wiki rows")
    return out


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_wiki_views())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
