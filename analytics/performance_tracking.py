"""Track performance of allocation methods."""

from __future__ import annotations

import datetime as dt
from typing import Dict

import pandas as pd

from database import alloc_perf_coll
from service.logger import get_logger


log = get_logger("alloc_perf")


def track_allocation_performance(weekly: pd.DataFrame) -> Dict[str, float]:
    """Evaluate all allocation methods on the latest returns and store results.

    The function computes the one-period return for each weighting scheme and
    persists summary metrics so users can review which allocator performs best
    over time.
    """

    if weekly.empty:
        return {}

    from .allocation_engine import (
        _tangency_weights,
        risk_parity_weights,
        min_variance_weights,
    )

    methods = {
        "tangency": _tangency_weights,
        "risk_parity": lambda df: risk_parity_weights(df.cov()),
        "min_variance": lambda df: min_variance_weights(df.cov()),
    }
    last_row = weekly.tail(1)
    results: Dict[str, float] = {}
    for name, func in methods.items():
        try:
            w = func(weekly)
            if not w:
                continue
            w_series = pd.Series(w).reindex(weekly.columns).fillna(0)
            ret = float((last_row @ w_series).iloc[0]) if not last_row.empty else 0.0
            results[name] = ret
            if alloc_perf_coll:
                alloc_perf_coll.update_one(
                    {"date": dt.date.today(), "method": name},
                    {"$set": {"ret": ret}},
                    upsert=True,
                )
        except Exception as exc:  # pragma: no cover - best effort logging
            log.debug({"perf_track_error": str(exc), "method": name})
    return results


__all__ = ["track_allocation_performance"]
