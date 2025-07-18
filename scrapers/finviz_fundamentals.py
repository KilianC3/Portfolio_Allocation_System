from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Dict, Optional

import yfinance as yf
from bs4 import BeautifulSoup, Tag
try:
    from playwright.sync_api import sync_playwright
except Exception:  # noqa: S110
    sync_playwright = None

from database import init_db
from service.logger import get_logger


log = get_logger(__name__)


def _random_user_agent() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ]
    return random.choice(agents)


def _short_pause(min_seconds: float = 0.8, max_seconds: float = 1.6) -> None:
    """Sleep briefly to avoid hammering Finviz."""
    time.sleep(random.uniform(min_seconds, max_seconds))


_YF_KEYS = [
    "trailingPE",
    "forwardPE",
    "pegRatio",
    "priceToBook",
    "dividendYield",
    "beta",
    "profitMargins",
    "operatingMargins",
    "returnOnAssets",
    "returnOnEquity",
    "revenueGrowth",
    "earningsGrowth",
    "freeCashflow",
    "enterpriseToRevenue",
    "enterpriseToEbitda",
    "marketCap",
    "debtToEquity",
    "shortRatio",
]


def _finviz_snapshot(symbol: str) -> Dict[str, str]:
    _short_pause()
    if sync_playwright is None:
        raise RuntimeError("playwright not installed")
    with sync_playwright() as pw:
        browser = pw.firefox.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": _random_user_agent()})
        page.goto(f"https://finviz.com/quote.ashx?t={symbol}")
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="snapshot-table2")
    data: Dict[str, str] = {}
    if isinstance(table, Tag):
        cells = [c.get_text(strip=True) for c in table.find_all("td")]
        for i in range(0, len(cells) - 1, 2):
            data[cells[i]] = cells[i + 1]
    return data


def _yf_extended(symbol: str) -> Dict[str, Optional[float]]:
    _short_pause()
    info = yf.Ticker(symbol).info
    return {k: info.get(k) for k in _YF_KEYS}


def fetch_fundamentals(symbol: str) -> Dict[str, float | None | str]:
    """Return selected Finviz and yfinance fields for ``symbol``."""
    log.info(f"fetch_fundamentals start symbol={symbol}")
    init_db()
    snap = _finviz_snapshot(symbol)
    info = _yf_extended(symbol)

    def _num(val: str | float | None) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace("%", "").replace(",", ""))
        except ValueError:
            return None

    data = {
        "short_ratio": _num(snap.get("Short Ratio") or info.get("shortRatio")),
        "insider_buying": _num(snap.get("Insider Trans")),
        "fetched_at_utc": datetime.utcnow().isoformat(),
    }
    log.info("fetch_fundamentals complete")
    return data
