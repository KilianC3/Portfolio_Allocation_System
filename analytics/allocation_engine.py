"""Enhanced portfolio allocation engine."""

from __future__ import annotations

from typing import Mapping, Optional, Callable

import numpy as np
import pandas as pd

from sklearn.covariance import LedoitWolf

from service.config import MAX_ALLOC, MIN_ALLOC
from database import db, alloc_log_coll
from service.logger import get_logger


def _clean_returns(df: pd.DataFrame, z_thresh: float = 5.0) -> pd.DataFrame:
    """Clip extreme outliers based on a z-score threshold."""
    if df.empty:
        return df
    mu = df.mean()
    std = df.std(ddof=0).replace(0, np.nan)
    z = (df - mu) / std
    cleaned = df.mask(z.abs() > z_thresh, mu, axis=1)
    return cleaned.fillna(mu)


_log = get_logger("alloc")


def _log_to_db(
    table: pd.DataFrame, extras: Optional[Mapping[str, float]] = None
) -> None:
    """Persist scoring table for audit; ignore failures."""
    try:
        coll = alloc_log_coll if alloc_log_coll else db["alloc_log"]
        doc = table.reset_index().rename(columns={"index": "symbol"}).to_dict()
        if extras:
            doc.update(extras)
        coll.insert_one(doc)
    except Exception as exc:  # pragma: no cover - logging should not fail tests
        _log.warning({"db_error": str(exc)})


def _tangency_weights(
    weekly: pd.DataFrame,
    w_prev: Optional[Mapping[str, float]] = None,
    target_vol: float = 0.11,
    turnover_thresh: float = 0.005,
    risk_free: float = 0.0,
) -> dict[str, float]:
    mu = weekly.mean()
    _log.debug({"mu": mu.to_dict()})
    lw = LedoitWolf().fit(weekly.fillna(0))
    cov = pd.DataFrame(lw.covariance_, index=weekly.columns, columns=weekly.columns)
    _log.debug({"cov": cov.to_dict()})
    inv = np.linalg.pinv(cov.values)
    excess = mu - risk_free
    w = pd.Series(np.maximum(inv @ excess.values, 0), index=weekly.columns)
    if w.sum() == 0:
        w[:] = 1
    w /= w.sum()

    port_vol = float(np.sqrt(w @ cov @ w) * np.sqrt(52))
    _log.debug({"port_vol": port_vol})
    if not np.isfinite(port_vol) or port_vol > 5 or port_vol == 0:
        _log.warning({"anomaly": "vol", "value": port_vol})
        if w_prev:
            return dict(w_prev)
        w[:] = 1 / len(w)
        port_vol = float(np.sqrt(w @ cov @ w) * np.sqrt(52))
    if port_vol > 0:
        w *= target_vol / port_vol

    w = w.clip(lower=MIN_ALLOC, upper=MAX_ALLOC)
    w /= w.sum()

    if w_prev:
        prev = pd.Series(w_prev).reindex(w.index).fillna(0)
        mask = (w - prev).abs() <= turnover_thresh
        w[mask] = prev[mask]
        w /= w.sum()

    table = pd.DataFrame({"mu": mu, "weight": w})
    _log.info({"weights": w.to_dict(), "vol": port_vol})
    _log_to_db(table, {"target_vol": target_vol, "portfolio_vol": port_vol})
    return w.to_dict()


def risk_parity_weights(cov: pd.DataFrame) -> dict[str, float]:
    """Compute naive risk parity weights given a covariance matrix."""
    if cov.empty:
        return {}
    n = len(cov)
    w = np.ones(n) / n
    for _ in range(100):
        port_var = float(w @ cov.values @ w)
        mrc = cov.values @ w
        rc = w * mrc
        target = port_var / n
        diff = rc - target
        if np.max(np.abs(diff)) < 1e-8:
            break
        w -= diff / (mrc + 1e-12)
        w = np.maximum(w, 0)
        if w.sum() == 0:
            w[:] = 1 / n
        w /= w.sum()
    return {c: float(w[i]) for i, c in enumerate(cov.columns)}


def saa_weights(weekly: pd.DataFrame) -> dict[str, float]:
    """Strategic asset allocation with fixed equal-weight targets."""
    if weekly.empty:
        return {}
    n = len(weekly.columns)
    return {c: 1 / n for c in weekly.columns}


def taa_weights(weekly: pd.DataFrame) -> dict[str, float]:
    """Tactical allocation that tilts weights toward recent winners."""
    if weekly.empty:
        return {}
    base = pd.Series(1 / len(weekly.columns), index=weekly.columns)
    last = weekly.tail(1).iloc[0]
    tilt = base * (1 + last)
    tilt = tilt.clip(lower=0)
    if tilt.sum() == 0:
        return base.to_dict()
    tilt /= tilt.sum()
    return tilt.to_dict()


def dynamic_weights(weekly: pd.DataFrame) -> dict[str, float]:
    """Dynamic allocation using simple momentum over the last month."""
    if weekly.empty:
        return {}
    mom = (1 + weekly.tail(4)).prod() - 1
    w = mom.clip(lower=0)
    if w.sum() == 0:
        w[:] = 1 / len(w)
    else:
        w /= w.sum()
    return w.to_dict()


def min_variance_weights(cov: pd.DataFrame) -> dict[str, float]:
    """Return global minimum variance portfolio weights."""
    if cov.empty:
        return {}
    inv = np.linalg.pinv(cov.values)
    ones = np.ones(len(cov))
    w = inv @ ones
    if w.sum() == 0:
        w[:] = 1
    w /= w.sum()
    return {c: float(w[i]) for i, c in enumerate(cov.columns)}


def compute_weights(
    ret_df: pd.DataFrame,
    w_prev: Optional[Mapping[str, float]] = None,
    target_vol: float = 0.11,
    turnover_thresh: float = 0.005,
    risk_free: float = 0.0,
    method: str = "max_sharpe",
) -> dict[str, float]:
    """Return portfolio weights for the chosen allocation method."""

    target_vol = max(0.10, min(0.12, target_vol))

    if ret_df.empty:
        return {}

    weekly = (1 + ret_df).resample("W-FRI").prod() - 1
    weeks = len(weekly)
    if weeks > 36:
        weekly = weekly.tail(36)
    if weeks < 4 or weekly.empty:
        _log.info({"fallback": "equal_weights", "reason": "insufficient"})
        return {c: 1 / len(ret_df.columns) for c in ret_df.columns}

    weekly = _clean_returns(weekly)
    avg = weekly.mean(axis=1)
    for col in weekly.columns:
        mask = weekly[col].isna()
        if mask.any():
            weekly.loc[mask, col] = avg[mask]

    lw = LedoitWolf().fit(weekly.fillna(0))
    cov = pd.DataFrame(lw.covariance_, index=weekly.columns, columns=weekly.columns)

    dispatch: dict[str, Callable[..., dict[str, float]]] = {
        "max_sharpe": lambda: _tangency_weights(
            weekly,
            w_prev=w_prev,
            target_vol=target_vol,
            turnover_thresh=turnover_thresh,
            risk_free=risk_free,
        ),
        "risk_parity": lambda: risk_parity_weights(cov),
        "min_variance": lambda: min_variance_weights(cov),
        "saa": lambda: saa_weights(weekly),
        "taa": lambda: taa_weights(weekly),
        "dynamic": lambda: dynamic_weights(weekly),
        "tangency": lambda: _tangency_weights(
            weekly,
            w_prev=w_prev,
            target_vol=target_vol,
            turnover_thresh=turnover_thresh,
            risk_free=risk_free,
        ),
    }
    if method not in dispatch:
        raise ValueError(f"unknown method: {method}")

    return dispatch[method]()
