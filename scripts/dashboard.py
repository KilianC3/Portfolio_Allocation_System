#!/usr/bin/env python3
"""CLI dashboard for inspecting database health and table samples."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
from database import init_db, db, db_ping
from service.scheduler import StrategyScheduler

try:
    from service.config import API_TOKEN
except Exception:

    def _parse_simple_yaml(path: Path) -> dict:
        data = {}
        if path.exists():
            for raw in path.read_text().splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip("'\"")
        return data

    cfg = ROOT / "service" / "config.yaml"
    API_TOKEN = _parse_simple_yaml(cfg).get("API_TOKEN")

init_db()

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


def main() -> None:
    print("=== DB HEALTH ===")
    status = {"status": "ok" if db_ping() else "fail"}
    print(status)

    sched = StrategyScheduler()
    sched.start()
    jobs = [
        {
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in sched.scheduler.get_jobs()
    ]
    sched.stop()

    print("\n=== SCHEDULE ===")
    if jobs:
        print(pd.DataFrame(jobs).to_string(index=False))

    for name in TABLES:
        data = list(db[name].find({}).limit(5))
        print(f"\n=== {name} ({len(data)}) ===")
        if data:
            print(pd.DataFrame(data).to_string(index=False))


if __name__ == "__main__":
    main()
