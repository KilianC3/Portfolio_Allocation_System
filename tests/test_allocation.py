import pandas as pd
from allocation_engine import compute_weights


def test_compute_weights_sum():
    data = {
        'pf1': [0.01, -0.02, 0.015, 0.005] * 10,
        'pf2': [0.0, 0.01, -0.005, 0.002] * 10
    }
    df = pd.DataFrame(data)
    w = compute_weights(df)
    assert abs(sum(w.values()) - 1.0) < 1e-6
