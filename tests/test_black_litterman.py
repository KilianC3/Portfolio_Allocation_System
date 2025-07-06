import numpy as np
import pandas as pd

from analytics.blacklitterman import market_implied_returns, black_litterman_posterior


def test_black_litterman_posterior():
    cov = pd.DataFrame([[0.04, 0.006], [0.006, 0.09]], index=["A", "B"], columns=["A", "B"])
    mkt_w = pd.Series([0.6, 0.4], index=["A", "B"])
    pi = market_implied_returns(cov, mkt_w, risk_aversion=2.5)
    P = pd.DataFrame(np.eye(2), index=["A", "B"], columns=["A", "B"])
    Q = pd.Series([0.03, 0.05], index=["A", "B"])
    posterior = black_litterman_posterior(cov, pi, P, Q)
    assert posterior.index.tolist() == ["A", "B"]
    assert posterior.isna().sum() == 0
