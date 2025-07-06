import datetime as dt
from typing import List, Optional, cast
from bs4 import BeautifulSoup
from bs4.element import Tag
from config import QUIVER_RATE_SEC
from infra.rate_limiter import AsyncRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll
from pymongo.collection import Collection
from infra.data_store import append_snapshot

contracts_coll: Collection = db["gov_contracts"] if db else pf_coll
rate = AsyncRateLimiter(1, QUIVER_RATE_SEC)

async def fetch_gov_contracts() -> List[dict]:
    """Scrape top government contract recipients from QuiverQuant."""
    url = "https://www.quiverquant.com/sources/governmentcontracts"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data: List[dict] = []
    now = dt.datetime.utcnow()
    if table:
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 3:
                item = {
                    "ticker": cells[0],
                    "value": cells[1],
                    "date": cells[2],
                    "_retrieved": now,
                }
                data.append(item)
                contracts_coll.update_one(
                    {"ticker": item["ticker"], "date": item["date"]},
                    {"$set": item},
                    upsert=True,
                )
    append_snapshot("gov_contracts", data)
    return data


if __name__ == "__main__":
    import asyncio
    asyncio.run(fetch_gov_contracts())
