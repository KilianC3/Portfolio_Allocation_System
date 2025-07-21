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

contracts_coll = db["gov_contracts"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
log = get_scraper_logger(__name__)


async def fetch_gov_contracts() -> List[dict]:
    """Scrape top government contract recipients from QuiverQuant."""
    log.info("fetch_gov_contracts start")
    init_db()
    url = "https://www.quiverquant.com/sources/govcontracts"
    with scrape_latency.labels("gov_contracts").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("gov_contracts").inc()
            log.warning(f"fetch_gov_contracts failed: {exc}")
            raise
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
    log.info(f"fetched {len(data)} gov contract rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_gov_contracts())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
