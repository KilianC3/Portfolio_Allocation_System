import pandas as pd
import numpy as np
from pathlib import Path
import runpy

bl = runpy.run_path(
    Path(__file__).resolve().parents[1] / "analytics" / "blacklitterman.py"
)
market_implied_returns = bl["market_implied_returns"]
black_litterman_posterior = bl["black_litterman_posterior"]
from analytics.robust import minmax_portfolio
from analytics.covariance import estimate_covariance
from analytics.utils import portfolio_metrics
from pathlib import Path


def test_all_models():
    cov = pd.DataFrame([[0.1, 0.05], [0.05, 0.2]], index=["A", "B"], columns=["A", "B"])
    weights = pd.Series([0.6, 0.4], index=["A", "B"])
    pi = market_implied_returns(cov, weights)
    P = pd.DataFrame([[1, -1]], columns=["A", "B"])
    Q = pd.Series([0.02])
    post = black_litterman_posterior(cov, pi, P, Q)
    mm = minmax_portfolio(post, cov)
    rand = pd.DataFrame(np.random.randn(50, 2), columns=["A", "B"])
    cov_est = estimate_covariance(rand)
    metrics = portfolio_metrics(pd.Series(np.random.randn(50)))
    assert not post.isna().any() and not cov_est.isna().any().any()
    print(mm.iloc[0], list(metrics.values())[0])


from strategies.biotech_event import BiotechBinaryEventBasket


def test_biotech_check(monkeypatch):
    class FakeTicker:
        info = {"industry": "Biotechnology"}

    monkeypatch.setattr("yfinance.Ticker", lambda s: FakeTicker())
    assert BiotechBinaryEventBasket.is_biotech("AAPL")
