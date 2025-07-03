import datetime as dt
from typing import List
from bs4 import BeautifulSoup
from config import QUIVER_RATE_SEC
from infra.rate_limiter import AsyncRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll
from infra.data_store import append_snapshot

politician_coll = db["politician_trades"] if db else pf_coll
rate = AsyncRateLimiter(1, QUIVER_RATE_SEC)

async def fetch_politician_trades() -> List[dict]:
    url = "https://www.quiverquant.com/sources/politician-trading"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    data = []
    now = dt.datetime.utcnow()
    if table:
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 5:
                item = {
                    "politician": cells[0],
                    "ticker": cells[1],
                    "transaction": cells[2],
                    "amount": cells[3],
                    "date": cells[4],
                    "_retrieved": now,
                }
                data.append(item)
                politician_coll.update_one(
                    {
                        "politician": item["politician"],
                        "ticker": item["ticker"],
                        "date": item["date"],
                    },
                    {"$set": item},
                    upsert=True,
                )
    append_snapshot("politician_trades", data)
    return data


if __name__ == "__main__":
    import asyncio
    asyncio.run(fetch_politician_trades())
