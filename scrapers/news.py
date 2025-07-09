from __future__ import annotations

import datetime as dt
from typing import List
from bs4 import BeautifulSoup

from config import QUIVER_RATE_SEC
from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from database import db, pf_coll
from infra.data_store import append_snapshot

news_coll = db["news_headlines"] if db else pf_coll
rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)


async def fetch_stock_news(limit: int = 50) -> List[dict]:
    """Scrape recent stock news from Finviz."""
    url = "https://finviz.com/news.ashx?v=3"
    async with rate:
        html = await scrape_get(url)
    soup = BeautifulSoup(html, "html.parser")
    rows: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    for tr in soup.select("tr.news_table-row"):
        date_cell = tr.select_one("td.news_date-cell")
        link_cell = tr.select_one("td.news_link-cell")
        if not date_cell or not link_cell:
            continue
        head = link_cell.find("a", class_="nn-tab-link")
        if not head:
            continue
        headline = head.get_text(strip=True)
        link = head.get("href")
        sym_anchor = link_cell.find(
            "a", href=lambda x: isinstance(x, str) and x.startswith("/quote.ashx?t=")
        )
        ticker = ""
        if sym_anchor and sym_anchor.get("href"):
            ticker = sym_anchor["href"].split("t=")[1].split("&")[0]
        source = link_cell.find("span", class_="news_date-cell")
        item = {
            "ticker": ticker,
            "headline": headline,
            "link": link,
            "source": source.get_text(strip=True) if source else "",
            "time": date_cell.get_text(strip=True),
            "_retrieved": now,
        }
        news_coll.insert_one(item)
        rows.append(item)
        if len(rows) >= limit:
            break
    append_snapshot("news_headlines", rows)
    return rows


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(fetch_stock_news(3)))
