import numpy as np
import pandas as pd

from analytics import allocation_engine


def risk_parity_weights_python(cov: pd.DataFrame) -> np.ndarray:
    n = len(cov)
    w = np.ones(n) / n
    for _ in range(100):
        port_var = float(w @ cov.values @ w)
        mrc = cov.values @ w
        rc = w * mrc
        target = port_var / n
        diff = rc - target
        if np.max(np.abs(diff)) < 1e-8:
            break
        w -= diff / (mrc + 1e-12)
        w = np.maximum(w, 0)
        if w.sum() == 0:
            w[:] = 1 / n
        w /= w.sum()
    return w


def test_rust_risk_parity_matches_python():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(4, 4))
    cov = pd.DataFrame(a @ a.T, columns=list("ABCD"), index=list("ABCD"))
    expected = risk_parity_weights_python(cov)
    rust_result = allocation_engine.risk_parity_weights(cov)
    rust_vec = np.array([rust_result[c] for c in cov.columns])
    assert np.allclose(rust_vec, expected)
