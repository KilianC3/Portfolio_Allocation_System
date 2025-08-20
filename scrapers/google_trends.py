import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
from typing import Callable, Any, List, Optional, cast

from bs4 import BeautifulSoup
from bs4.element import Tag

async_playwright: Any
try:
    from playwright.async_api import async_playwright as _ap

    HAVE_PW = True
    async_playwright = _ap
except Exception:  # noqa: S110
    HAVE_PW = False
    async_playwright = None

from service.config import QUIVER_RATE_SEC
from infra.rate_limiter import DynamicRateLimiter
from infra.smart_scraper import get as scrape_get
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger

log = get_scraper_logger(__name__)

trends_coll = db["google_trends"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


def parse_google_trends(html: str, limit: int | None = None) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = cast(Optional[Tag], soup.find("table"))
    rows: List[dict] = []
    if not table:
        return rows
    for tr in cast(List[Tag], table.find_all("tr"))[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 2:
            continue
        ticker = tds[0].upper()
        score = tds[1]
        date = (
            tds[2]
            if len(tds) > 2
            else dt.datetime.now(dt.timezone.utc).date().isoformat()
        )
        try:
            score_f = float(score)
        except Exception:
            continue
        rows.append({"ticker": ticker, "score": score_f, "date": date})
        if limit and len(rows) >= limit:
            break
    return rows


async def fetch_google_trends(limit: int | None = None) -> List[dict]:
    """Scrape Google Trends scores from QuiverQuant.

    Parameters
    ----------
    limit:
        Maximum number of rows to return. ``None`` fetches all rows.
    """
    log.info("fetch_google_trends start")
    init_db()
    url = "https://www.quiverquant.com/googletrends/"
    rows: List[dict] = []
    with scrape_latency.labels("google_trends").time():
        # Static fetch first
        try:
            async with rate:
                html = await scrape_get(url)
            rows = parse_google_trends(html, limit)
        except Exception as exc:  # pragma: no cover - network optional
            log.exception(f"google_trends http failed: {exc}")
            scrape_errors.labels("google_trends").inc()
        # Playwright fallback
        if not rows and HAVE_PW:
            try:
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, timeout=60000)
                    await page.wait_for_selector("table", timeout=60000)
                    html = await page.content()
                    await browser.close()
                rows = parse_google_trends(html, limit)
            except Exception as exc:  # pragma: no cover - network optional
                log.exception(f"google_trends playwright failed: {exc}")

    now = dt.datetime.now(dt.timezone.utc)
    for item in rows:
        item["_retrieved"] = now
        trends_coll.update_one(
            {"ticker": item["ticker"], "date": item["date"]},
            {"$set": item},
            upsert=True,
        )
    if rows:
        append_snapshot("google_trends", rows)
    log.info("fetched %d google trend rows", len(rows))
    return rows


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_google_trends())
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
