import datetime as dt
from typing import List, Optional, cast
from bs4 import BeautifulSoup
from bs4.element import Tag

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot

app_reviews_coll = db["app_reviews"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_app_reviews() -> List[dict]:
    """Scrape app review hype scores from QuiverQuant."""
    init_db()
    url = "https://www.quiverquant.com/sources/appratings"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    if table:
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 3:
                item = {
                    "ticker": cells[0],
                    "hype": cells[1],
                    "date": cells[2],
                    "_retrieved": now,
                }
                data.append(item)
                app_reviews_coll.update_one(
                    {"ticker": item["ticker"], "date": item["date"]},
                    {"$set": item},
                    upsert=True,
                )
    append_snapshot("app_reviews", data)
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_app_reviews())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
