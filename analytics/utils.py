"""Utility functions for portfolio analytics."""

import math
from typing import Optional

import numpy as np
import pandas as pd


def lambda_from_half_life(h: int) -> float:
    """Return the exponential decay factor for a given half-life ``h``."""
    return 1 - 2 ** (-1 / h)


def sharpe(r: pd.Series, rf: float = 0.0) -> float:
    """Annualised Sharpe ratio of a returns series."""
    std = r.std(ddof=0)
    if std == 0:
        return 0.0
    return (r.mean() - rf) / std * math.sqrt(252)


def var_cvar(r: pd.Series, level: float = 0.95) -> tuple[float, float]:
    """Return VaR and CVaR for a return series."""
    var = np.quantile(r, 1 - level)
    cvar = r[r <= var].mean()
    return float(var), float(cvar)


def alpha_beta(r: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    """Annualised alpha and beta relative to a benchmark."""
    bench = benchmark.reindex(r.index).fillna(0)
    cov = np.cov(r, bench, ddof=0)
    beta = 0.0 if cov[1, 1] == 0 else cov[0, 1] / cov[1, 1]
    alpha = (r.mean() - beta * bench.mean()) * 252
    return float(alpha), float(beta)


def max_drawdown(r: pd.Series) -> float:
    """Maximum drawdown of a returns series."""
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())


def period_return(r: pd.Series, days: int) -> float:
    """Cumulative return over the last ``days`` observations."""
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
    """Compute a comprehensive set of portfolio metrics."""
    metrics = {
        "ret_1d": period_return(r, 1),
        "ret_7d": period_return(r, 7),
        "ret_30d": period_return(r, 30),
        "ret_3m": period_return(r, 63),
        "ret_6m": period_return(r, 126),
        "ret_1y": period_return(r, 252),
        "ret_2y": period_return(r, 504),
        "cumulative_return": cumulative_return(r),
        "sharpe": sharpe(r, rf),
        "sortino": sortino(r, rf),
        "max_drawdown": max_drawdown(r),
        "annual_vol": r.std(ddof=0) * math.sqrt(252),
        "annual_std": r.std(ddof=0) * math.sqrt(252),
        "win_rate": float((r > 0).mean()),
        "avg_win": float(r[r > 0].mean() if (r > 0).any() else 0.0),
        "avg_loss": float(r[r < 0].mean() if (r < 0).any() else 0.0),
    }
    days = len(r.dropna())
    if days:
        metrics["cagr"] = (1 + cumulative_return(r)) ** (252 / days) - 1
    else:
        metrics["cagr"] = 0.0
    var, cvar = var_cvar(r)
    metrics["var"] = var
    metrics["cvar"] = cvar

    if benchmark is not None and not benchmark.empty:
        a, b = alpha_beta(r, benchmark)
        metrics["alpha"] = a
        metrics["beta"] = b
        metrics["tracking_error"] = tracking_error(r, benchmark)
        metrics["information_ratio"] = information_ratio(r, benchmark)
        metrics["treynor_ratio"] = 0.0 if b == 0 else (r.mean() - rf) / b
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
    "lambda_from_half_life",
]
