"""Utility functions for portfolio analytics."""

"""Utility functions for portfolio analytics."""

import math
from typing import Optional

import numpy as np
import pandas as pd


def sharpe(r: pd.Series, rf: float = 0.0) -> float:
    """Annualised Sharpe ratio of a returns series."""
    if r.std(ddof=0) == 0:
        return 0.0
    return (r.mean() - rf) / r.std(ddof=0) * math.sqrt(252)


def var_cvar(r: pd.Series, level: float = 0.95) -> tuple[float, float]:
    """Return VaR and CVaR for a return series.

    The metrics follow the definitions used throughout the documentation:

    .. math::
        VaR_\alpha = -\operatorname{quantile}_{1-\alpha}(r_t)

    .. math::
        CVaR_\alpha = -\mathbb{E}[r_t \mid r_t \le -VaR_\alpha]
    """
    var = np.quantile(r, 1 - level)
    cvar = r[r <= var].mean()
    return var, cvar


def alpha_beta(r: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    """Annualised alpha and beta relative to a benchmark."""
    benchmark = benchmark.reindex(r.index).fillna(0)
    cov = np.cov(r, benchmark, ddof=0)
    beta = 0.0 if cov[1, 1] == 0 else cov[0, 1] / cov[1, 1]
    alpha = (r.mean() - beta * benchmark.mean()) * 252
    return float(alpha), float(beta)


def max_drawdown(r: pd.Series) -> float:
    """Maximum drawdown of a returns series."""
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())


def period_return(r: pd.Series, days: int) -> float:
    """Cumulative return over the last ``days`` observations."""
    if r.empty:
        return 0.0
    segment = r.dropna().iloc[-days:]
    if segment.empty:
        return 0.0
    return float((segment + 1).prod() - 1)


def sortino(r: pd.Series, rf: float = 0.0) -> float:
    """Annualised Sortino ratio using downside deviation."""
    downside = r[r < 0].std(ddof=0)
    if downside == 0:
        return 0.0
    return (r.mean() - rf) / downside * math.sqrt(252)


def cumulative_return(r: pd.Series) -> float:
    """Total cumulative return for the period."""
    return float((1 + r).prod() - 1)


def tracking_error(r: pd.Series, benchmark: pd.Series) -> float:
    """Annualised tracking error of a portfolio versus a benchmark."""
    diff = r - benchmark.reindex(r.index).fillna(0)
    return diff.std(ddof=0) * math.sqrt(252)


def information_ratio(r: pd.Series, benchmark: pd.Series) -> float:
    """Information ratio relative to a benchmark."""
    te = tracking_error(r, benchmark)
    if te == 0:
        return 0.0
    return (r.mean() - benchmark.reindex(r.index).fillna(0).mean()) / te


def portfolio_metrics(
    r: pd.Series, benchmark: Optional[pd.Series] = None, rf: float = 0.0
) -> dict:
    """Compute a set of common portfolio metrics."""

    metrics = {
        "sharpe": sharpe(r, rf),
        "max_drawdown": max_drawdown(r),
        "sortino": sortino(r, rf),
        "cumulative_return": cumulative_return(r),
        "ret_7d": period_return(r, 7),
        "ret_30d": period_return(r, 30),
        "ret_1y": period_return(r, 252),
    }

    if benchmark is not None:
        a, b = alpha_beta(r, benchmark)
        metrics["alpha"] = a
        metrics["beta"] = b
        metrics["tracking_error"] = tracking_error(r, benchmark)
        metrics["information_ratio"] = information_ratio(r, benchmark)

    return metrics


__all__ = [
    "sharpe",
    "var_cvar",
    "alpha_beta",
    "max_drawdown",
    "sortino",
    "cumulative_return",
    "period_return",
    "tracking_error",
    "information_ratio",
    "portfolio_metrics",
]
