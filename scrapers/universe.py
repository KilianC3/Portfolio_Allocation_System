from __future__ import annotations

import io
import datetime as dt
from pathlib import Path
from typing import List

import pandas as pd
import requests

from database import init_db, universe_coll

DATA_DIR = Path("cache") / "universes"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SP500_URL = "https://datahub.io/core/s-and-p-500-companies/_r/-/data/constituents.csv"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
SP600_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
R2000_URL = "https://russellindexes.com/sites/us/files/indices/files/russell-2000-membership-list.csv"


def _tickers_from_wiki(url: str) -> List[str]:
    html = requests.get(url, timeout=30).text
    dfs = pd.read_html(html)
    out: list[str] = []
    for tbl in dfs:
        for col in tbl.columns:
            if str(col).lower().startswith(("ticker", "symbol")):
                out.extend(tbl[col].astype(str).str.upper())
                break
    return out


def _store_universe(index: str, tickers: List[str]) -> None:
    """Persist ticker list to the universe table."""
    init_db()
    now = dt.datetime.now(dt.timezone.utc)
    for sym in tickers:
        universe_coll.update_one(
            {"index": index, "symbol": sym},
            {"$set": {"index": index, "symbol": sym, "_retrieved": now}},
            upsert=True,
        )


def download_sp500(path: Path | None = None) -> Path:
    """Download S&P 500 constituents to CSV and database."""
    path = path or DATA_DIR / "sp500.csv"
    r = requests.get(SP500_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    tickers = df[df.columns[0]].astype(str).str.upper().tolist()
    pd.DataFrame(tickers, columns=["symbol"]).to_csv(path, index=False)
    _store_universe("sp500", tickers)
    return path


def download_sp1500(path: Path | None = None) -> Path:
    """Download S&P 1500 constituents to CSV."""
    path = path or DATA_DIR / "sp1500.csv"
    r = requests.get(SP500_URL, timeout=30)
    r.raise_for_status()
    df500 = pd.read_csv(io.StringIO(r.text))
    tickers = set(df500[df500.columns[0]].astype(str).str.upper())
    tickers.update(_tickers_from_wiki(SP400_URL))
    tickers.update(_tickers_from_wiki(SP600_URL))
    pd.DataFrame(sorted(tickers), columns=["symbol"]).to_csv(path, index=False)
    _store_universe("sp1500", list(tickers))
    return path


def download_russell2000(path: Path | None = None) -> Path:
    """Download Russell 2000 constituents to CSV."""
    path = path or DATA_DIR / "russell2000.csv"
    r = requests.get(R2000_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    col = next(
        (c for c in df.columns if "ticker" in c.lower() or "symbol" in c.lower()),
        df.columns[0],
    )
    tickers = df[col].astype(str).str.upper().tolist()
    pd.DataFrame(tickers, columns=["symbol"]).to_csv(path, index=False)
    _store_universe("russell2000", tickers)
    return path


def load_sp1500() -> List[str]:
    path = DATA_DIR / "sp1500.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


def load_sp500() -> List[str]:
    path = DATA_DIR / "sp500.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


def load_russell2000() -> List[str]:
    path = DATA_DIR / "russell2000.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()
