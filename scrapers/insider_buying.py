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

log = get_scraper_logger(__name__)

insider_buy_coll = db["insider_buying"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_insider_buying() -> List[dict]:
    """Scrape corporate insider filings from QuiverQuant."""
    log.info("fetch_insider_buying start")
    init_db()
    url = "https://www.quiverquant.com/insiders/"
    with scrape_latency.labels("insider_buying").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("insider_buying").inc()
            log.warning(f"fetch_insider_buying failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    if table:
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 4:
                item = {
                    "ticker": cells[0],
                    "exec": cells[1],
                    "shares": cells[2],
                    "date": cells[3],
                    "_retrieved": now,
                }
                data.append(item)
                insider_buy_coll.update_one(
                    {
                        "ticker": item["ticker"],
                        "exec": item["exec"],
                        "date": item["date"],
                    },
                    {"$set": item},
                    upsert=True,
                )
    append_snapshot("insider_buying", data)
    log.info(f"fetched {len(data)} insider buying rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_insider_buying())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
