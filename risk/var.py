"""Historical VaR calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def historical_var(returns: pd.Series, level: float = 0.95) -> float:
    """Return historical value at risk."""
    return float(np.quantile(returns, 1 - level))


def cvar(returns: pd.Series, level: float = 0.95) -> float:
    """Conditional value at risk."""
    var = historical_var(returns, level)
    return float(returns[returns <= var].mean())

__all__ = ["historical_var", "cvar"]
