from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
from typing import Any, Dict, List, cast
from bs4 import BeautifulSoup, Tag

from service.config import QUIVER_RATE_SEC
from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from database import db, pf_coll
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_scraper_logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

log = get_scraper_logger(__name__)

news_coll = db["news_headlines"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
_analyzer = SentimentIntensityAnalyzer()


async def fetch_stock_news(limit: int = 50) -> List[dict]:
    """Scrape recent stock news from Finviz."""
    log.info("fetch_stock_news start")
    url = "https://finviz.com/news.ashx?v=3"
    with scrape_latency.labels("news_headlines").time():
        try:
            async with rate:
                html = await scrape_get(url)
        except Exception as exc:
            scrape_errors.labels("news_headlines").inc()
            log.exception(f"fetch_stock_news failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []
    now = dt.datetime.now(dt.timezone.utc)
    for tr in soup.select("tr.news_table-row"):
        date_cell = tr.select_one("td.news_date-cell")
        link_cell = tr.select_one("td.news_link-cell")
        if not isinstance(date_cell, Tag) or not isinstance(link_cell, Tag):
            continue
        head = link_cell.find("a", class_="nn-tab-link")
        if not isinstance(head, Tag):
            continue
        headline = head.get_text(strip=True)
        link = head.get("href", "")
        sym_anchor = link_cell.find(
            "a", href=lambda x: isinstance(x, str) and x.startswith("/quote.ashx?t=")
        )
        href_val = sym_anchor.get("href") if isinstance(sym_anchor, Tag) else None
        ticker = (
            cast(str, href_val).split("t=")[1].split("&")[0]
            if isinstance(href_val, str)
            else ""
        )
        source_el = link_cell.find("span", class_="news_date-cell")
        source = source_el.get_text(strip=True) if isinstance(source_el, Tag) else ""
        item: Dict[str, Any] = {
            "ticker": ticker,
            "headline": headline,
            "link": link,
            "source": source,
            "time": date_cell.get_text(strip=True),
            "_retrieved": now,
            "sentiment": 0,
        }
        try:
            score = _analyzer.polarity_scores(headline)["compound"]
            item["sentiment"] = 1 if score > 0.05 else -1 if score < -0.05 else 0
        except Exception:
            item["sentiment"] = 0
        news_coll.insert_one(item)
        rows.append(item)
        if len(rows) >= limit:
            break
    append_snapshot("news_headlines", rows)
    log.info(f"fetched {len(rows)} news rows")
    return rows


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    rows = asyncio.run(fetch_stock_news(3))
    df = pd.DataFrame(rows)
    print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
