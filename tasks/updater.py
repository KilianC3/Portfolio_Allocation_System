"""Background task that periodically refreshes metrics and broadcasts updates."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Callable

from analytics.utils import portfolio_metrics
from database import metric_coll
from ws.hub import broadcast_message
import json


async def update_loop(fetch_returns: Callable[[], dict], interval: int = 300) -> None:
    """Periodically compute metrics from ``fetch_returns`` and broadcast.

    Parameters
    ----------
    fetch_returns: Callable[[], dict]
        Function returning a mapping ``{pf_id: pd.Series}`` of daily returns.
    interval: int
        Sleep interval between updates in seconds.
    """

    while True:
        data = fetch_returns()
        ts = dt.datetime.utcnow().isoformat()
        for pf_id, series in data.items():
            metrics = portfolio_metrics(series)
            metric_coll.update_one(
                {"portfolio_id": pf_id, "date": series.index[-1].date()},
                {"$set": metrics},
                upsert=True,
            )
            await broadcast_message(
                json.dumps(
                    {
                        "type": "metrics",
                        "portfolio_id": pf_id,
                        "date": ts,
                        "metrics": metrics,
                    }
                )
            )
        await asyncio.sleep(interval)
