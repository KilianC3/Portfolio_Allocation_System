"""Enhanced portfolio allocation engine."""

from __future__ import annotations

from typing import Mapping, Optional

import numpy as np
import pandas as pd

from sklearn.covariance import LedoitWolf

from config import MAX_ALLOC, MIN_ALLOC
from database import db, alloc_log_coll
from logger import get_logger


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


def compute_weights(
    ret_df: pd.DataFrame,
    w_prev: Optional[Mapping[str, float]] = None,
    target_vol: float = 0.08,
    turnover_thresh: float = 0.005,
    risk_free: float = 0.0,
) -> dict[str, float]:
    """Return tangency portfolio weights maximising the Sharpe ratio.

    Outlier weekly returns are clipped to reduce noise and the final portfolio
    volatility is checked for anomalies.  If an extreme value is detected the
    previous weights are returned to avoid destabilising the system.
    """

    if ret_df.empty:
        return {}

    weekly = (1 + ret_df).resample("W-FRI").prod() - 1
    weekly = weekly.tail(12)
    if len(weekly) < 4:
        _log.info({"fallback": "equal_weights", "reason": "insufficient data"})
        return {c: 1 / len(ret_df.columns) for c in ret_df.columns}

    weekly = _clean_returns(weekly)

    avg = weekly.mean(axis=1)
    for col in weekly.columns:
        mask = weekly[col].isna()
        if mask.any():
            weekly.loc[mask, col] = avg[mask]

    mu = weekly.mean()
    _log.debug({"mu": mu.to_dict()})
    lw = LedoitWolf().fit(weekly.fillna(0))
    cov = pd.DataFrame(lw.covariance_, index=weekly.columns, columns=weekly.columns)
    _log.debug({"cov": cov.to_dict()})
    inv = np.linalg.pinv(cov.values)
    excess = mu - risk_free
    w = pd.Series(inv @ excess.values, index=weekly.columns)
    if w.sum() == 0:
        w[:] = 1
    w /= w.sum()

    port_vol = float(np.sqrt(w @ cov @ w) * np.sqrt(52))
    _log.debug({"port_vol": port_vol})
    if not np.isfinite(port_vol) or port_vol > 5:
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
