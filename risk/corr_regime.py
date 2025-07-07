"""Rolling correlation regime detection."""

from __future__ import annotations

import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture


def _vol_regime(returns: pd.DataFrame, window: int, high: float) -> bool:
    """Return True if average rolling volatility exceeds ``high``."""
    vol = returns.rolling(window).std().dropna()
    if vol.empty:
        return False
    avg_vol = vol.mean(axis=1).iloc[-1]
    return float(avg_vol) > high


def correlation_regime(
    returns: pd.DataFrame,
    window: int = 60,
    high: float = 0.7,
    vol_high: float = 0.04,
) -> str:
    """Return the current correlation regime using a Gaussian mixture model.

    Parameters
    ----------
    returns : pd.DataFrame
        Asset returns.
    window : int, default 60
        Rolling window used to estimate average correlations.
    high : float, default 0.7
        Correlation threshold defining a high-correlation regime.
    vol_high : float, default 0.04
        Average rolling volatility above which the regime is considered ``"high"``.

    Returns
    -------
    str
        ``"high"`` if average correlation exceeds ``high`` else ``"normal"``.
    """
    if len(returns) < window:
        return "normal"
    roll_corr = returns.rolling(window).corr().groupby(level=0).mean().dropna()
    avg_corr = roll_corr.mean(axis=1)
    if len(avg_corr) < 2:
        avg = avg_corr.iloc[-1]
        if np.isnan(avg) or avg < high:
            return "high" if _vol_regime(returns, window, vol_high) else "normal"
        return "high"
    gm = GaussianMixture(n_components=2, random_state=0)
    gm.fit(avg_corr.to_frame("corr"))
    label = gm.predict([[avg_corr.iloc[-1]]])[0]
    means = gm.means_.ravel()
    corr_high = means[label] > high
    vol_high_flag = _vol_regime(returns, window, vol_high)
    if corr_high or vol_high_flag:
        return "high"
    return "normal"


__all__ = ["correlation_regime"]
