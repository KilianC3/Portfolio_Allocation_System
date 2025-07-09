from __future__ import annotations

import io
from pathlib import Path
from typing import List

import pandas as pd
import requests

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
    pd.DataFrame(df[col].astype(str).str.upper(), columns=["symbol"]).to_csv(
        path, index=False
    )
    return path


def load_sp1500() -> List[str]:
    path = DATA_DIR / "sp1500.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()


def load_russell2000() -> List[str]:
    path = DATA_DIR / "russell2000.csv"
    return pd.read_csv(path).symbol.dropna().astype(str).str.upper().tolist()
