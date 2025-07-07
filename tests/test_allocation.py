import numpy as np
import pandas as pd
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from allocation_engine import compute_weights


def test_compute_weights_caps_and_drift():
    np.random.seed(0)
    df = pd.DataFrame(np.random.randn(130, 3) / 100, columns=["A", "B", "C"])
    prev = {"A": 0.33, "B": 0.33, "C": 0.34}
    sector_map = {"A": "tech", "B": "tech", "C": "fin"}
    caps = {"tech": 0.6, "fin": 0.5}
    w = compute_weights(
        df, w_prev=prev, lambda_fee=0.1, sector_map=sector_map, sector_caps=caps
    )
    assert abs(sum(w.values()) - 1) < 1e-6
    assert w["A"] + w["B"] <= 0.6 + 1e-6
    w2 = compute_weights(
        df, w_prev=w, drift_band=0.05, sector_map=sector_map, sector_caps=caps
    )
    assert w2 == w
