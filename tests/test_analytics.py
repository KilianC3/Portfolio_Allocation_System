import pandas as pd
import numpy as np
from analytics import (
    sharpe,
    var_cvar,
    alpha_beta,
    max_drawdown,
    sortino,
    information_ratio,
)


def test_sharpe_basic():
    r = pd.Series([0.01, 0.02, -0.01, 0.03])
    s = sharpe(r)
    assert s > 0


def test_var_cvar():
    r = pd.Series(np.linspace(-0.05, 0.05, 100))
    var, cvar = var_cvar(r, level=0.95)
    assert var <= 0
    assert cvar <= var


def test_alpha_beta_and_mdd():
    r = pd.Series([0.01, 0.02, -0.01, 0.03] * 5)
    bench = pd.Series([0.008, 0.015, -0.005, 0.025] * 5)
    a, b = alpha_beta(r, bench)
    mdd = max_drawdown(r)
    assert isinstance(a, float) and isinstance(b, float)
    assert mdd <= 0


def test_sortino_and_info_ratio():
    r = pd.Series([0.01, 0.02, -0.03, 0.03, -0.015] * 4)
    bench = pd.Series([0.009, 0.015, -0.02, 0.02, -0.01] * 4)
    s = sortino(r)
    ir = information_ratio(r, bench)
    assert s > 0
    assert isinstance(ir, float)
