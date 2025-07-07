"""Account level metrics collection."""

from __future__ import annotations

import datetime as dt
from typing import Dict

from database import db
from execution.gateway import AlpacaGateway

account_coll = db["account_metrics"]


async def record_account(gateway: AlpacaGateway) -> Dict:
    """Fetch account equity from Alpaca and store it."""
    info = await gateway.account()
    doc = {
        "timestamp": dt.datetime.utcnow(),
        "paper": gateway.paper,
        "equity": float(info.get("equity", 0)),
        "last_equity": float(info.get("last_equity", 0)),
    }
    account_coll.insert_one(doc)
    return doc


__all__ = ["record_account", "account_coll"]
