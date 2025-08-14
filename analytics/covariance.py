"""Covariance estimation utilities."""

from __future__ import annotations

from typing import Literal

import pandas as pd
import covariance_rs


def ledoit_wolf_cov(returns: pd.DataFrame) -> pd.DataFrame:
    """Shrinkage covariance estimator (Ledoit-Wolf) via Rust."""
    cov = covariance_rs.ledoit_wolf_cov(returns.values.astype(float))
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)


def pca_factor_cov(returns: pd.DataFrame, n_components: int = 5) -> pd.DataFrame:
    """Factor-model covariance via PCA in Rust."""
    cov = covariance_rs.pca_factor_cov(
        returns.values.astype(float), int(n_components)
    )
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)


def estimate_covariance(
    returns: pd.DataFrame, method: Literal["ledoit", "pca"] = "ledoit"
) -> pd.DataFrame:
    """Return annualised covariance matrix."""
    if method == "pca":
        cov = pca_factor_cov(returns)
    else:
        cov = ledoit_wolf_cov(returns)
    return cov * 252


__all__ = ["estimate_covariance", "ledoit_wolf_cov", "pca_factor_cov"]
