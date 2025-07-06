"""Simplified Black-Litterman utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def market_implied_returns(
    cov: pd.DataFrame, weights: pd.Series, risk_aversion: float = 2.5
) -> pd.Series:
    """Calculate equilibrium returns from market weights."""
    mu = risk_aversion * cov.values @ weights.values
    return pd.Series(mu, index=cov.index)


def black_litterman_posterior(
    cov: pd.DataFrame,
    pi: pd.Series,
    P: pd.DataFrame,
    Q: pd.Series,
    tau: float = 0.05,
    omega: pd.DataFrame | None = None,
) -> pd.Series:
    """Compute posterior expected returns."""
    tau_sigma = tau * cov.values
    if omega is None:
        omega = np.diag(np.diag(P.values @ tau_sigma @ P.values.T))
    middle = np.linalg.inv(P.values @ tau_sigma @ P.values.T + omega)
    mu = (
        np.linalg.inv(np.linalg.inv(tau_sigma) + P.values.T @ middle @ P.values)
        @ (np.linalg.inv(tau_sigma) @ pi.values + P.values.T @ middle @ Q.values)
    )
    return pd.Series(mu, index=cov.index)

__all__ = ["market_implied_returns", "black_litterman_posterior"]
