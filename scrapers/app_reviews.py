import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
from typing import List, Optional, cast
from bs4 import BeautifulSoup
from bs4.element import Tag

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger
from .utils import get_column_map, validate_row

app_reviews_coll = db["app_reviews"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
log = get_scraper_logger(__name__)


async def fetch_app_reviews() -> List[dict]:
    """Scrape app review hype scores from QuiverQuant."""
    log.info("fetch_app_reviews start")
    init_db()
    url = "https://www.quiverquant.com/sources/appratings"
    with scrape_latency.labels("app_reviews").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("app_reviews").inc()
            log.exception(f"fetch_app_reviews failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    if table:
        col_map = get_column_map(
            table,
            {"ticker": ["ticker", "symbol"], "hype": ["hype"], "date": ["date"]},
        )
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            item = {
                field: cells[idx] for field, idx in col_map.items() if idx < len(cells)
            }
            if len(item) == len(col_map):
                item["_retrieved"] = now
                item = validate_row(item, numeric_fields={"hype": float}, log=log)
                if not item:
                    continue
                data.append(item)
                app_reviews_coll.update_one(
                    {"ticker": item["ticker"], "date": item["date"]},
                    {"$set": item},
                    upsert=True,
                )
    append_snapshot("app_reviews", data)
    log.info(f"fetched {len(data)} app review rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_app_reviews())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
