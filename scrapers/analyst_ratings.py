from __future__ import annotations

import datetime as dt
import json
from typing import Iterable, List, Optional

import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup, Tag
from typing import Callable, Any

async_playwright: Callable[..., Any] | None
try:
    from playwright.async_api import async_playwright as _ap
    async_playwright = _ap
except Exception:  # noqa: S110 - optional dependency
    async_playwright = None

from infra.smart_scraper import get as scrape_get
from infra.rate_limiter import DynamicRateLimiter
from service.config import QUIVER_RATE_SEC
from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

analyst_coll = db["analyst_ratings"] if db else pf_coll

rate = DynamicRateLimiter(1, QUIVER_RATE_SEC)
log = get_logger(__name__)

# URL scraped via Playwright
BENZINGA_UPGRADES_URL = "https://www.benzinga.com/analyst-ratings/upgrades"


async def _fetch_ticker(sym: str) -> pd.DataFrame:
    """Return recent upgrade records for ``sym`` from Benzinga."""
    log.info(f"_fetch_ticker start sym={sym}")
    records = await fetch_analyst_ratings(limit=200)
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df[df["ticker"].str.upper() == sym.upper()]  # filter for ticker
    df["date"] = pd.to_datetime(df["date_utc"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.assign(rating="upgrade")[["date", "rating"]]
    log.info(f"fetched {len(df)} analyst rows for {sym}")
    return df


TIERS = [
    "Sell",
    "Underperform",
    "Underweight",
    "Hold",
    "Neutral",
    "Market Perform",
    "Perform",
    "Equal-Weight",
    "Sector Perform",
    "In-Line",
    "Peer Perform",
    "Accumulate",
    "Buy",
    "Outperform",
    "Overweight",
    "Strong Buy",
]


def _tier_rank(r: str) -> int:
    try:
        return TIERS.index(r.title())
    except ValueError:
        return -1


def _get(row: dict, keys: Iterable[str]) -> Optional[str]:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return str(row[k])
    return None


def _find_rows(obj: object) -> Optional[List[dict]]:
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and (
            "ticker" in obj[0] or "symbol" in obj[0]
        ):
            return obj  # type: ignore[return-value]
        for item in obj:
            out = _find_rows(item)
            if out is not None:
                return out
    elif isinstance(obj, dict):
        for v in obj.values():
            out = _find_rows(v)
            if out is not None:
                return out
    return None


async def fetch_analyst_ratings(limit: int = 15) -> List[dict]:
    """Fetch latest analyst upgrades from Benzinga."""
    log.info("fetch_analyst_ratings start")
    init_db()
    url = BENZINGA_UPGRADES_URL
    with scrape_latency.labels("analyst_ratings").time():
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
        except Exception as exc:  # pragma: no cover - network optional
            scrape_errors.labels("analyst_ratings").inc()
            log.warning(f"fetch_analyst_ratings failed: {exc}")
            raise
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not isinstance(script, Tag) or not script.string:
        raise RuntimeError("__NEXT_DATA__ not found")
    data = json.loads(script.string)
    rows = _find_rows(data)
    if rows is None:
        raise RuntimeError("analyst rows not found in page data")

    out: List[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    for row in rows:
        if len(out) >= limit:
            break
        rating_cur = _get(row, ["rating_current", "rating", "new_rating"])
        rating_prev = _get(
            row,
            [
                "rating_prior",
                "rating_previous",
                "old_rating",
                "previous_rating",
            ],
        )
        pt_cur = _get(row, ["pt_current", "price_target", "pt_after"])
        pt_prev = _get(row, ["pt_prior", "price_target_prior", "pt_before"])
        pct = _get(row, ["pt_pct_change", "pt_change_pct"])
        pct_val: Optional[float] = None
        if pct is not None:
            try:
                pct_val = float(str(pct).replace("%", ""))
            except Exception:
                pct_val = None
        elif pt_cur is not None and pt_prev is not None:
            try:
                pct_val = (
                    (float(pt_cur) - float(pt_prev)) / float(pt_prev) * 100
                )
            except Exception:
                pct_val = None

        is_upgrade = False
        if rating_cur and rating_prev:
            is_upgrade = _tier_rank(rating_cur) > _tier_rank(rating_prev)

        include = is_upgrade or (pct_val is not None and pct_val >= 5)
        if not include:
            continue

        if is_upgrade and pct_val is not None and pct_val >= 5:
            action = "UPGRADE_PT_RAISE"
        elif is_upgrade:
            action = "UPGRADE"
        else:
            action = "PT_RAISE"

        item = {
            "date_utc": _get(row, ["date", "date_utc", "time"]) or now.isoformat(),
            "ticker": _get(row, ["ticker", "symbol"]) or "",
            "company": _get(row, ["company", "name", "company_name"]) or "",
            "analyst": _get(row, ["analyst", "firm", "analyst_name"]) or "",
            "rating_prior": rating_prev or "",
            "rating_current": rating_cur or "",
            "pt_prior": pt_prev or "",
            "pt_current": pt_cur or "",
            "pt_pct_change": pct_val,
            "action": action,
            "_retrieved": now,
        }
        out.append(item)
    append_snapshot("analyst_ratings", out)
    log.info(f"fetched {len(out)} analyst rows")
    return out


async def fetch_changes(symbols: Iterable[str], weeks: int = 4) -> pd.DataFrame:
    """Summary counts of recent upgrades per ticker."""
    cutoff = pd.Timestamp.today(tz=dt.timezone.utc) - pd.Timedelta(weeks=weeks)
    all_records = await fetch_analyst_ratings(limit=200)
    df = pd.DataFrame(all_records)
    if df.empty:
        return pd.DataFrame(columns=[
            "symbol",
            "upgrades",
            "downgrades",
            "total",
            "targetMeanPrice",
            "numAnalystOpinions",
        ])
    df["date"] = pd.to_datetime(df["date_utc"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[df["date"] >= cutoff]
    rows: List[dict] = []
    for sym in symbols:
        sub = df[df["ticker"].str.upper() == sym.upper()]
        up = int(sub["action"].str.contains("UPGRADE").sum())
        info = {}
        try:
            info = yf.Ticker(sym).info
        except Exception:
            info = {}
        rows.append(
            dict(
                symbol=sym,
                upgrades=up,
                downgrades=0,
                total=len(sub),
                targetMeanPrice=info.get("targetMeanPrice"),
                numAnalystOpinions=info.get("numberOfAnalystOpinions"),
            )
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import asyncio
    import pandas as pd

    df = pd.DataFrame(asyncio.run(fetch_analyst_ratings()))
    print(df.to_csv(sep="\t", index=False))
