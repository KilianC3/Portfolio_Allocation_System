import datetime as dt
import json
from typing import List

from config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, wiki_coll
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors

wiki_collection = wiki_coll if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_wiki_views(page: str = "Apple_Inc", days: int = 7) -> List[dict]:
    """Fetch Wikipedia page views via the Wikimedia API."""

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
        except Exception:
            scrape_errors.labels("wiki_views").inc()
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
    return data


if __name__ == "__main__":
    import asyncio

    asyncio.run(fetch_wiki_views())
