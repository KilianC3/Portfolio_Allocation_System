import pandas as pd
import numpy as np
from analytics import sharpe, var_cvar


def test_sharpe_basic():
    r = pd.Series([0.01, 0.02, -0.01, 0.03])
    s = sharpe(r)
    assert s > 0


def test_var_cvar():
    r = pd.Series(np.linspace(-0.05, 0.05, 100))
    var, cvar = var_cvar(r, level=0.95)
    assert var <= 0
    assert cvar <= var
