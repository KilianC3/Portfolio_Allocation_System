import pandas as pd
from risk.corr_regime import correlation_regime


def test_high_correlation_regime():
    data = pd.DataFrame({"A": [0.05] * 60, "B": [0.05] * 60})
    regime = correlation_regime(data, window=20, high=0.8, vol_high=0.04)
    assert regime == "high"


def test_normal_correlation_regime():
    rng = pd.date_range("2023-01-01", periods=60)
    data = pd.DataFrame(
        {
            "A": pd.Series(0.01, index=rng) + pd.Series(range(60)) / 10000,
            "B": pd.Series(-0.01, index=rng) + pd.Series(range(60))[::-1] / 10000,
        }
    )
    regime = correlation_regime(data, window=20, high=0.8, vol_high=0.04)
    assert regime == "normal"
