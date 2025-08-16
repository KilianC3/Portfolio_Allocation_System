import random
import time
from typing import Dict, Optional

import requests

from service.logger import get_scraper_logger

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA})

log = get_scraper_logger(__name__)

BASE = "https://data.sec.gov/api/xbrl"

_CIK_CACHE: dict[str, int] = {}


def _sleep():
    time.sleep(0.2 + random.random() * 0.3)


def _ticker_to_cik(symbol: str) -> Optional[int]:
    sym = symbol.lower()
    if sym in _CIK_CACHE:
        return _CIK_CACHE[sym]
    try:
        _sleep()
        resp = session.get(f"{BASE}/ticker/{sym}.json", timeout=10)
        if resp.status_code != 200:
            return None
        cik = int(resp.json().get("cik_str"))
        _CIK_CACHE[sym] = cik
        return cik
    except Exception:
        log.warning("edgar cik lookup failed for %s", symbol)
        return None


def _latest_fact(facts: dict, *names: str) -> Optional[float]:
    for name in names:
        node = facts.get(name)
        if not node or "units" not in node:
            continue
        units = next(iter(node["units"].values()), [])
        if units:
            val = units[-1].get("val")
            if val is not None:
                return float(val)
    return None


def fetch_edgar_facts(symbol: str) -> Dict[str, float]:
    """Return a minimal fundamentals dict from SEC EDGAR."""
    cik = _ticker_to_cik(symbol)
    if not cik:
        return {}
    try:
        _sleep()
        resp = session.get(f"{BASE}/companyfacts/CIK{cik:010d}.json", timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
    except Exception:
        log.warning("edgar facts fetch failed for %s", symbol)
        return {}
    facts = data.get("facts", {})
    out: Dict[str, float] = {}
    cash = _latest_fact(facts, "CashAndCashEquivalentsAtCarryingValue")
    if cash is not None:
        out["totalCash"] = cash
    debt = _latest_fact(facts, "Debt", "LongTermDebt")
    if debt is not None:
        out["totalDebt"] = debt
    shares = _latest_fact(
        facts,
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    )
    if shares is not None:
        out["sharesOutstanding"] = shares
    return out


__all__ = ["fetch_edgar_facts"]
