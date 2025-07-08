"""Historical value at risk utilities.

The functions implement basic risk metrics used throughout the project.

Historical VaR is defined as

.. math::
    \text{VaR}_{\alpha} = -\operatorname{quantile}_{1-\alpha}(r_t)

which estimates the loss threshold not exceeded with probability ``alpha`` over
the sample of returns ``r_t``.

Conditional VaR is

.. math::
    \text{CVaR}_{\alpha} = -\mathbb{E}[r_t \mid r_t \le -\text{VaR}_{\alpha}]

and measures the expected loss given that returns fall below the corresponding
VaR level.
"""

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
