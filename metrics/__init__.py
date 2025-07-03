"""Performance metrics utilities with Prometheus gauges."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd
from prometheus_client import Gauge

alpha_gauge = Gauge("strategy_alpha", "Alpha")
beta_gauge = Gauge("strategy_beta", "Beta")
maxdd_gauge = Gauge("strategy_max_drawdown", "Maximum drawdown")
var_gauge = Gauge("strategy_var", "Value at Risk")
cvar_gauge = Gauge("strategy_cvar", "Conditional Value at Risk")
tail_gauge = Gauge("strategy_tail_ratio", "Tail ratio")


def alpha_beta(r: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    benchmark = benchmark.reindex(r.index).fillna(0)
    cov = np.cov(r, benchmark, ddof=0)
    beta = 0.0 if cov[1, 1] == 0 else cov[0, 1] / cov[1, 1]
    alpha = (r.mean() - beta * benchmark.mean()) * 252
    alpha_gauge.set(alpha)
    beta_gauge.set(beta)
    return float(alpha), float(beta)


def max_drawdown(r: pd.Series) -> float:
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1
    v = float(dd.min())
    maxdd_gauge.set(v)
    return v


def value_at_risk(r: pd.Series, level: float = 0.95) -> float:
    v = float(np.quantile(r, 1 - level))
    var_gauge.set(v)
    return v


def conditional_var(r: pd.Series, level: float = 0.95) -> float:
    var = value_at_risk(r, level)
    cv = float(r[r <= var].mean())
    cvar_gauge.set(cv)
    return cv


def tail_ratio(r: pd.Series) -> float:
    pos = r[r > 0].sum()
    neg = abs(r[r < 0].sum())
    if neg == 0:
        tr = math.inf
    else:
        tr = pos / neg
    tail_gauge.set(tr)
    return float(tr)

__all__ = [
    "alpha_beta",
    "max_drawdown",
    "value_at_risk",
    "conditional_var",
    "tail_ratio",
    "alpha_gauge",
    "beta_gauge",
    "maxdd_gauge",
    "var_gauge",
    "cvar_gauge",
    "tail_gauge",
]
