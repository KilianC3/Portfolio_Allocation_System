"""Account level metrics collection."""

from __future__ import annotations

import datetime as dt
from typing import Dict

from database import db
from pathlib import Path
import csv
from execution.gateway import AlpacaGateway

account_coll = db["account_metrics"]


async def record_account(gateway: AlpacaGateway) -> Dict:
    """Fetch account equity from Alpaca and store it."""
    info = await gateway.account()
    doc = {
        "timestamp": dt.datetime.now(dt.timezone.utc),
        "paper": gateway.paper,
        "equity": float(info.get("equity", 0)),
        "last_equity": float(info.get("last_equity", 0)),
    }
    account_coll.insert_one(doc)
    csv_path = Path("cache") / "account_metrics.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    header = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(doc.keys()))
        if header:
            writer.writeheader()
        row = {
            k: (v.isoformat() if isinstance(v, dt.datetime) else v)
            for k, v in doc.items()
        }
        writer.writerow(row)
    return doc


__all__ = ["record_account", "account_coll"]
