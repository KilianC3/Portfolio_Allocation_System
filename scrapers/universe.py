from __future__ import annotations

import io
import datetime as dt
from pathlib import Path
from typing import List

import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Callable, Any

sync_playwright: Callable[..., Any] | None
try:
    from playwright.sync_api import sync_playwright as _sp

    sync_playwright = _sp
except Exception:  # noqa: S110 - optional dependency
    sync_playwright = None

from database import init_db, universe_coll
from io import StringIO
from service.logger import get_scraper_logger

DATA_DIR = Path("cache") / "universes"
DATA_DIR.mkdir(parents=True, exist_ok=True)
log = get_scraper_logger(__name__)

SP500_URL = "https://datahub.io/core/s-and-p-500-companies/_r/-/data/constituents.csv"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
R2000_URL = "https://en.wikipedia.org/wiki/List_of_Russell_2000_companies"
FINANCHLE_URL = "https://financhle.com/russell2000-companies-by-weight"
MARKETSCREENER_URL = (
    "https://www.marketscreener.com/quote/index/" "RUSSELL-2000-157793769/components/"
)


def _tickers_from_wiki(url: str) -> List[str]:
    html = requests.get(url, timeout=30).text
    dfs = pd.read_html(StringIO(html))
    out: list[str] = []
    for tbl in dfs:
        for col in tbl.columns:
            if str(col).lower().startswith(("ticker", "symbol")):
                out.extend(tbl[col].astype(str).str.upper())
                break
    return out


def _tickers_from_financhle() -> List[str]:
    """Scrape Russell 2000 tickers from Financhle using Playwright."""
    if sync_playwright is None:
        raise RuntimeError("playwright not installed")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.goto(FINANCHLE_URL)
        try:
            page.click("button.show-full-list-button", timeout=5000)
            page.wait_for_timeout(3000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    df = pd.read_html(StringIO(str(table)))[0]
    if "Ticker" in df.columns:
        col = "Ticker"
    else:
        col = df.columns[0]
    return df[col].astype(str).str.upper().tolist()


def _tickers_from_marketscreener() -> List[str]:
    """Scrape Russell 2000 tickers from MarketScreener."""
    if sync_playwright is None:
        raise RuntimeError("playwright not installed")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.goto(MARKETSCREENER_URL)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    df = pd.read_html(StringIO(str(table)))[0]
    col = [
        c
        for c in df.columns
        if "symbol" in str(c).lower() or "ticker" in str(c).lower()
    ]
    if col:
        col = col[0]
    else:
        col = df.columns[0]
    return df[col].astype(str).str.upper().tolist()


def _store_universe(tickers: List[str], index_name: str) -> None:
    """Persist ticker list to the unified universe table."""
    init_db()
    now = dt.datetime.now(dt.timezone.utc)
    for sym in tickers:
        universe_coll.update_one(
            {"symbol": sym},
            {
                "$set": {
                    "symbol": sym,
                    "index_name": index_name,
                    "_retrieved": now,
                }
            },
            upsert=True,
        )


def download_sp500(path: Path | None = None) -> Path:
    """Download S&P 500 constituents to CSV and database."""
    log.info("download_sp500 start")
    path = path or DATA_DIR / "sp500.csv"
    r = requests.get(SP500_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    tickers = df[df.columns[0]].astype(str).str.upper().tolist()
    pd.DataFrame(tickers, columns=["symbol"]).to_csv(path, index=False)
    _store_universe(tickers, "S&P500")
    log.info(f"download_sp500 wrote {len(tickers)} symbols")
    return path


def download_sp400(path: Path | None = None) -> Path:
    """Download S&P 400 constituents to CSV."""
    log.info("download_sp400 start")
    path = path or DATA_DIR / "sp400.csv"
    tickers = _tickers_from_wiki(SP400_URL)
    pd.DataFrame(sorted(tickers), columns=["symbol"]).to_csv(path, index=False)
    _store_universe(list(tickers), "S&P400")
    log.info(f"download_sp400 wrote {len(tickers)} symbols")
    return path


def download_russell2000(path: Path | None = None) -> Path:
    """Download Russell 2000 constituents to CSV."""
    log.info("download_russell2000 start")
    path = path or DATA_DIR / "russell2000.csv"
    try:
        tickers = _tickers_from_wiki(R2000_URL)
    except Exception:
        tickers = []
    if not tickers:
        try:
            tickers = _tickers_from_financhle()
        except Exception as exc:
            log.warning(f"financhle scrape failed: {exc}")
            try:
                tickers = _tickers_from_marketscreener()
            except Exception as exc2:
                log.warning(f"marketscreener scrape failed: {exc2}")
                tickers = []
    pd.DataFrame(sorted(tickers), columns=["symbol"]).to_csv(path, index=False)
    _store_universe(list(tickers), "Russell2000")
    log.info(f"download_russell2000 wrote {len(tickers)} symbols")
    return path


def load_sp400() -> List[str]:
    path = DATA_DIR / "sp400.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


def load_sp500() -> List[str]:
    path = DATA_DIR / "sp500.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


def load_russell2000() -> List[str]:
    path = DATA_DIR / "russell2000.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download ticker universes")
    parser.add_argument(
        "--refresh-universe",
        action="store_true",
        help="download all universes and store to the database",
    )
    args = parser.parse_args()

    if args.refresh_universe:
        sp500 = download_sp500()
        sp400 = download_sp400()
        r2000 = download_russell2000()
        for p in (sp500, sp400, r2000):
            df = pd.read_csv(p)
            print(f"ROWS={len(df)} COLUMNS={df.shape[1]}")
