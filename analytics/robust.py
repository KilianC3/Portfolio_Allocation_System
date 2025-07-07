"""Robust portfolio optimisation utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def minmax_portfolio(
    mu: pd.Series,
    cov: pd.DataFrame,
    gamma: float = 1.0,
    delta: float = 0.05,
) -> pd.Series:
    """Return weights from a simple min-max mean-variance optimisation.

    The worst-case covariance is approximated by scaling ``cov`` by ``1 + delta``.
    """
    worst = cov * (1 + delta)
    inv = np.linalg.pinv(gamma * worst)
    w = inv @ mu.values
    w = np.clip(w, 0, None)
    if w.sum() > 0:
        w = w / w.sum()
    else:
        w = np.ones(len(mu)) / len(mu)
    return pd.Series(w, index=mu.index)


__all__ = ["minmax_portfolio"]
