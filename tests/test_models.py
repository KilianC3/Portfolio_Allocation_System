import pandas as pd
import numpy as np
from analytics.robust import minmax_portfolio
from analytics.covariance import estimate_covariance
from analytics.utils import portfolio_metrics
from analytics.allocation_engine import compute_weights
from pathlib import Path


def test_all_models():
    cov = pd.DataFrame([[0.1, 0.05], [0.05, 0.2]], index=["A", "B"], columns=["A", "B"])
    mu = pd.Series([0.02, 0.03], index=["A", "B"])
    mm = minmax_portfolio(mu, cov)
    rand = pd.DataFrame(np.random.randn(50, 2), columns=["A", "B"])
    cov_est = estimate_covariance(rand)
    metrics = portfolio_metrics(pd.Series(np.random.randn(50)))
    assert not cov_est.isna().any().any()
    assert not mm.isna().any()
    print(mm.iloc[0], list(metrics.values())[0])


from strategies.smallcap_momentum import SmallCapMomentum


def test_biotech_check(monkeypatch):
    class FakeTicker:
        info = {"industry": "Biotechnology"}

    monkeypatch.setattr("yfinance.Ticker", lambda s: FakeTicker())
    assert SmallCapMomentum.is_biotech("AAPL")


def test_update_ticker_returns(monkeypatch):
    import analytics.tracking as trk

    dates = pd.date_range("2020-01-01", periods=10)

    def fake_download(symbols, *a, **k):
        syms = symbols if isinstance(symbols, list) else [symbols]
        close = pd.DataFrame({s: np.linspace(1, 2, 10) for s in syms}, index=dates)
        return pd.concat({"Close": close}, axis=1)

    monkeypatch.setattr(trk.yf, "download", fake_download)
    rec = []

    class Coll:
        def update_one(self, *a, **k):
            rec.append(a)

    monkeypatch.setattr(trk, "ticker_return_coll", Coll())
    trk.update_ticker_returns(["AAPL"])
    assert rec


def test_compute_weights_simple():
    dates = pd.date_range("2024-01-01", periods=90)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.01, len(dates)),
        },
        index=dates,
    )
    w = compute_weights(df)
    assert abs(sum(w.values()) - 1) < 1e-6 and set(w) == {"A", "B"}


def test_compute_weights_anomaly():
    dates = pd.date_range("2024-01-01", periods=90)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 5.0, len(dates)),
            "B": np.random.normal(0, 5.0, len(dates)),
        },
        index=dates,
    )
    prev = {"A": 0.6, "B": 0.4}
    w = compute_weights(df, w_prev=prev)
    assert w == prev


def test_compute_weights_insufficient_data():
    dates = pd.date_range("2024-01-01", periods=14)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.01, len(dates)),
            "C": np.random.normal(0, 0.01, len(dates)),
        },
        index=dates,
    )
    w = compute_weights(df)
    assert all(abs(v - 1 / 3) < 1e-6 for v in w.values())
