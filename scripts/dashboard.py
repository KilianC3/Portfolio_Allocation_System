#!/usr/bin/env python3
"""CLI dashboard for inspecting API health and table samples."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import requests
import pandas as pd
from service.config import API_TOKEN

BASE_URL = os.environ.get("API_BASE", "http://localhost:8001")
TOKEN = API_TOKEN or os.environ.get("API_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

TABLES = [
    "portfolios",
    "trades",
    "metrics",
    "politician_trades",
    "lobbying",
    "wiki_views",
    "dc_insider_scores",
    "gov_contracts",
    "app_reviews",
    "google_trends",
    "analyst_ratings",
    "news_headlines",
    "insider_buying",
    "reddit_mentions",
    "sp500_index",
    "universe",
    "ticker_scores",
    "top_scores",
    "account_metrics_paper",
    "account_metrics_live",
    "system_logs",
]


def _fetch_json(path: str) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    print("=== HEALTH ===")
    print(_fetch_json("/health"))
    print("\n=== READY ===")
    print(_fetch_json("/readyz"))

    print("\n=== SCHEDULE ===")
    jobs = _fetch_json("/scheduler/jobs").get("jobs", [])
    if jobs:
        print(pd.DataFrame(jobs).to_string(index=False))

    for name in TABLES:
        data = _fetch_json(f"/db/{name}?limit=5").get("records", [])
        print(f"\n=== {name} ({len(data)}) ===")
        if data:
            print(pd.DataFrame(data).to_string(index=False))


if __name__ == "__main__":
    main()
