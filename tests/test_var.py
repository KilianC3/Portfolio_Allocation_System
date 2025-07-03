import pandas as pd
from risk.var import historical_var, cvar


def test_var_cvar():
    r = pd.Series([0.01, -0.02, 0.03, -0.04, 0.05])
    v = historical_var(r, level=0.8)
    cv = cvar(r, level=0.8)
    assert v < 0
    assert cv <= v
