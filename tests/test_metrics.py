import pandas as pd
import numpy as np
import pytest

from metrics import alpha_beta, max_drawdown, value_at_risk, conditional_var, tail_ratio

@pytest.mark.asyncio
async def test_metrics_values():
    r = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01])
    bench = pd.Series([0.01, 0.0, 0.02, -0.01, 0.0])
    a, b = alpha_beta(r, bench)
    assert isinstance(a, float) and isinstance(b, float)
    md = max_drawdown(r)
    assert md <= 0
    var = value_at_risk(r, 0.8)
    cv = conditional_var(r, 0.8)
    assert cv <= var
    tr = tail_ratio(r)
    assert tr > 0
