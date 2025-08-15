"""Background task that periodically refreshes metrics and broadcasts updates."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Callable, Any

from analytics.utils import (
    portfolio_metrics,
    aggregate_daily_returns_exposure,
)
from analytics.performance_tracking import track_allocation_performance
from database import metric_coll
from ws.hub import broadcast_message
from service.cache import invalidate_prefix
import json


async def update_loop(
    fetch_returns: Callable[[], dict[str, Any]], interval: int = 300
) -> None:
    """Periodically compute metrics from ``fetch_returns`` and broadcast.

    Parameters
    ----------
    fetch_returns: Callable[[], dict]
        Function returning a mapping ``{pf_id: pd.Series}`` of daily returns.
    interval: int
        Sleep interval between updates in seconds.
    """

    sem = asyncio.Semaphore(4)

    async def run_sync(func: Callable, *args: Any, **kwargs: Any) -> Any:
        async with sem:
            return await asyncio.to_thread(func, *args, **kwargs)

    while True:
        data = await run_sync(fetch_returns)
        ts = dt.datetime.utcnow().isoformat()
        for pf_id, payload in data.items():
            asset_returns = None
            if isinstance(payload, tuple):
                if len(payload) == 3:
                    series, exposure, asset_returns = payload
                else:
                    series, exposure = payload
            else:
                series, exposure = payload, None

            await run_sync(
                aggregate_daily_returns_exposure,
                pf_id,
                series,
                exposure,
                metric_coll,
            )
            if asset_returns is not None:
                try:
                    await run_sync(track_allocation_performance, asset_returns)
                except Exception:  # pragma: no cover - best effort
                    pass
            metrics = await run_sync(portfolio_metrics, series)
            await run_sync(
                metric_coll.update_one,
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
            await run_sync(invalidate_prefix, f"metrics:{pf_id}")
        await asyncio.sleep(interval)
