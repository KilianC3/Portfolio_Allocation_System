"""Enhanced portfolio allocation engine."""

from __future__ import annotations

from typing import Mapping, Optional, Literal

import numpy as np
import pandas as pd

from sklearn.covariance import LedoitWolf
from scipy.cluster.hierarchy import linkage, dendrogram

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


def _hrp_weights(cov: pd.DataFrame) -> pd.Series:
    """Return hierarchical risk parity weights."""
    corr = cov.corr()
    dist = np.sqrt(0.5 * (1 - corr))
    link = linkage(dist, method="single")
    sort_ix = dendrogram(link, no_plot=True)["leaves"]
    items = corr.index[sort_ix].tolist()

    def _cluster_var(items: list[str]) -> float:
        sub = cov.loc[items, items]
        inv_var = 1 / np.diag(sub)
        w = inv_var / inv_var.sum()
        return float(w @ sub.values @ w)

    w = pd.Series(1.0, index=items)
    clusters = [items]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        split = len(cluster) // 2
        left = cluster[:split]
        right = cluster[split:]
        v_l = _cluster_var(left)
        v_r = _cluster_var(right)
        alloc_l = 1 - v_l / (v_l + v_r)
        alloc_r = 1 - alloc_l
        w[left] *= alloc_l
        w[right] *= alloc_r
        clusters.insert(0, right)
        clusters.insert(0, left)
    return w / w.sum()


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
    method: Literal["rp", "hrp"] = "rp",
) -> dict[str, float]:
    """Return portfolio weights using risk parity or hierarchical risk parity.

    Outlier weekly returns are clipped to reduce noise and the final portfolio
    volatility is checked for anomalies.  If an extreme value is detected the
    previous weights are returned to avoid destabilising the system.
    """

    if ret_df.empty:
        return {}

    weekly = (1 + ret_df).resample("W-FRI").prod() - 1
    weekly = weekly.tail(12)
    if weekly.empty:
        return {c: 1 / len(ret_df.columns) for c in ret_df.columns}

    weekly = _clean_returns(weekly)

    avg = weekly.mean(axis=1)
    sample_size: dict[str, int] = {}
    for col in weekly.columns:
        mask = weekly[col].isna()
        sample_size[col] = int((~mask).sum())
        if mask.any():
            weekly.loc[mask, col] = avg[mask]

    vol = weekly.std(ddof=0) * np.sqrt(52)

    momentum = {}
    beta_score = {}
    for col in weekly.columns:
        n = sample_size[col]
        s = weekly[col].iloc[-n:] if n > 0 else pd.Series(dtype=float)
        v = vol[col] if vol[col] != 0 else np.nan
        r1 = s.iloc[-1] if n >= 1 else 0.0
        r4 = (1 + s.iloc[-min(4, n) :]).prod() - 1 if n else 0.0
        r12 = (1 + s).prod() - 1 if n else 0.0
        parts = []
        if n >= 1:
            parts.append(r1 / v if v == v else 0.0)
        if n >= 4:
            parts.append(r4 / v if v == v else 0.0)
        if n:
            parts.append(r12 / v if v == v else 0.0)
        momentum[col] = float(np.mean(parts)) if parts else 0.0
        std = s.std(ddof=0)
        beta_score[col] = float(r12 / (std / np.sqrt(n))) if std > 0 and n else 0.0

    momentum = pd.Series(momentum)
    beta_series = pd.Series(beta_score)

    lw = LedoitWolf().fit(weekly.fillna(0))
    cov = pd.DataFrame(lw.covariance_, index=weekly.columns, columns=weekly.columns)

    if method == "hrp":
        base = _hrp_weights(cov)
    else:
        base = 1 / vol.replace(0, np.inf)
        base /= base.sum()

    w = base * (1 + momentum * beta_series)
    w = w.clip(lower=0)
    if w.sum() == 0:
        w += 1
    w /= w.sum()

    port_vol = float(np.sqrt(w @ cov @ w) * np.sqrt(52))
    if not np.isfinite(port_vol) or port_vol > 5:
        _log.warning({"anomaly": "vol", "value": port_vol})
        if w_prev:
            return dict(w_prev)
        return base.to_dict()
    if port_vol > 0:
        w *= target_vol / port_vol

    w = w.clip(lower=MIN_ALLOC, upper=MAX_ALLOC)
    w /= w.sum()

    if w_prev:
        prev = pd.Series(w_prev).reindex(w.index).fillna(0)
        mask = (w - prev).abs() <= turnover_thresh
        w[mask] = prev[mask]
        w /= w.sum()

    table = pd.DataFrame(
        {
            "vol": vol,
            "momentum": momentum,
            "beta": beta_series,
            "base_weight": base,
            "weight": w,
        }
    )

    _log.info({"weights": w.to_dict(), "vol": port_vol})
    _log_to_db(table, {"target_vol": target_vol, "portfolio_vol": port_vol})
    return w.to_dict()
