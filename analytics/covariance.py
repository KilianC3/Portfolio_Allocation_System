"""Covariance estimation utilities."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from sklearn.decomposition import PCA


def ledoit_wolf_cov(returns: pd.DataFrame) -> pd.DataFrame:
    """Shrinkage covariance estimator (Ledoit-Wolf)."""
    lw = LedoitWolf().fit(returns)
    cov = pd.DataFrame(lw.covariance_, index=returns.columns, columns=returns.columns)
    return cov


def pca_factor_cov(returns: pd.DataFrame, n_components: int = 5) -> pd.DataFrame:
    """Factor-model covariance via PCA."""
    n_comp = min(n_components, len(returns.columns))
    returns_demeaned = returns - returns.mean()
    pca = PCA(n_components=n_comp)
    scores = pca.fit_transform(returns_demeaned)
    loadings = pca.components_.T
    factor_cov = np.cov(scores, rowvar=False)
    cov = loadings @ factor_cov @ loadings.T
    resid = returns_demeaned - scores @ loadings.T
    diag = np.diag(resid.var(axis=0, ddof=0))
    cov += diag
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
