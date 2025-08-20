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

log = get_scraper_logger(__name__)

insider_buy_coll = db["insider_buying"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_insider_buying(limit: int | None = None) -> List[dict]:
    """Scrape corporate insider filings from QuiverQuant.

    Parameters
    ----------
    limit:
        Maximum number of rows to return. ``None`` fetches all rows.
    """
    log.info("fetch_insider_buying start")
    init_db()
    url = "https://www.quiverquant.com/insiders/"
    with scrape_latency.labels("insider_buying").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("insider_buying").inc()
            log.exception(f"fetch_insider_buying failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    data: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if table:
        col_map = get_column_map(
            table,
            {
                "ticker": ["ticker", "symbol"],
                "exec": ["exec", "executive", "insider"],
                "shares": ["shares"],
                "date": ["date"],
            },
        )
        for row in cast(List[Tag], table.find_all("tr"))[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            item = {
                field: cells[idx] for field, idx in col_map.items() if idx < len(cells)
            }
            if len(item) == len(col_map):
                validated = validate_row(item, numeric_fields={"shares": int}, log=log)
                if not validated:
                    continue
                validated["_retrieved"] = now
                data.append(validated)
                insider_buy_coll.update_one(
                    {
                        "ticker": validated["ticker"],
                        "exec": validated["exec"],
                        "date": validated["date"],
                    },
                    {"$set": validated},
                    upsert=True,
                )
                if limit and len(data) >= limit:
                    break
    append_snapshot("insider_buying", data)
    log.info(f"fetched {len(data)} insider buying rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_insider_buying())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
