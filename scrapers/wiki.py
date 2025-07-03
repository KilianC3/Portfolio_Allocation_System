import datetime as dt
from typing import List
from bs4 import BeautifulSoup
from config import QUIVER_RATE_SEC
from infra.rate_limiter import AsyncRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, wiki_coll

wiki_collection = wiki_coll if db else pf_coll
rate = AsyncRateLimiter(1, QUIVER_RATE_SEC)

async def fetch_wiki_views() -> List[dict]:
    """Scrape most viewed company pages from QuiverQuant."""
    url = "https://www.quiverquant.com/sources/wikipedia"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    data = []
    now = dt.datetime.utcnow()
    if table:
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 3:
                item = {
                    "ticker": cells[0],
                    "views": cells[1],
                    "date": cells[2],
                    "_retrieved": now,
                }
                data.append(item)
                wiki_collection.update_one(
                    {"ticker": item["ticker"], "date": item["date"]},
                    {"$set": item},
                    upsert=True,
                )
    return data
