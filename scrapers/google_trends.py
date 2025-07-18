import datetime as dt
from typing import List, Optional, cast
from bs4 import BeautifulSoup
from bs4.element import Tag
from typing import Callable, Any

async_playwright: Callable[..., Any] | None
try:
    from playwright.async_api import async_playwright as _ap
    async_playwright = _ap
except Exception:  # noqa: S110
    async_playwright = None

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

log = get_logger(__name__)

trends_coll = db["google_trends"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_google_trends() -> List[dict]:
    """Scrape Google Trends scores from QuiverQuant."""
    log.info("fetch_google_trends start")
    init_db()
    url = "https://www.quiverquant.com/googletrends/"
    with scrape_latency.labels("google_trends").time():
        try:
            if async_playwright is None:
                raise RuntimeError("playwright not installed")
            async with rate:
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url)
                    html = await page.content()
                    await browser.close()
            soup = BeautifulSoup(html, "html.parser")
            table = cast(Optional[Tag], soup.find("table"))
            if table is None:
                log.warning("google_trends: no <table> found – site layout may have changed")
                append_snapshot("google_trends", [])
                return []
            rows: List[dict] = []
            for row in cast(List[Tag], table.find_all("tr"))[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cells) >= 3:
                    rows.append({"ticker": cells[0], "score": cells[1], "date": cells[2]})
        except Exception as exc:
            scrape_errors.labels("google_trends").inc()
            log.warning(f"google_trends fetch failed: {exc}")
            raise
    data: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    for item in rows:
        item["_retrieved"] = now
        data.append(item)
        trends_coll.update_one(
            {"ticker": item["ticker"], "date": item["date"]},
            {"$set": item},
            upsert=True,
        )
    append_snapshot("google_trends", data)
    log.info(f"fetched {len(data)} google trend rows")
    return data


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_google_trends())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
