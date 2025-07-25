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

politician_coll = db["politician_trades"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
log = get_scraper_logger(__name__)


async def fetch_politician_trades() -> List[dict]:
    log.info("fetch_politician_trades start")
    init_db()
    url = "https://www.quiverquant.com/congresstrading/"
    with scrape_latency.labels("politician_trades").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("politician_trades").inc()
            log.exception(f"fetch_politician_trades failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data = []
    now = dt.datetime.now(dt.timezone.utc)
    if table:
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
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
    log.info(f"fetched {len(data)} politician trade rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_politician_trades())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
