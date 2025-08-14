"""Covariance estimation utilities."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

try:  # pragma: no cover - optional Rust extension
    import covariance_rs as _covariance_rs
except Exception:  # pragma: no cover - extension may be missing
    _covariance_rs = None


def ledoit_wolf_cov(returns: pd.DataFrame) -> pd.DataFrame:
    """Shrinkage covariance estimator (Ledoit–Wolf).

    Uses the Rust implementation when available and falls back to
    scikit-learn otherwise.
    """
    if _covariance_rs is not None:
        cov = _covariance_rs.ledoit_wolf_cov(returns.values.astype(float))
        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    from sklearn.covariance import LedoitWolf

    lw = LedoitWolf().fit(returns)
    return pd.DataFrame(lw.covariance_, index=returns.columns, columns=returns.columns)


def pca_factor_cov(returns: pd.DataFrame, n_components: int = 5) -> pd.DataFrame:
    """Factor-model covariance via PCA.

    Attempts to use the Rust extension and falls back to a Python
    implementation if the compiled module is unavailable.
    """
    if _covariance_rs is not None:
        cov = _covariance_rs.pca_factor_cov(
            returns.values.astype(float), int(n_components)
        )
        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    from sklearn.decomposition import PCA

    n_comp = min(int(n_components), returns.shape[1])
    returns_demeaned = returns - returns.mean()
    pca = PCA(n_components=n_comp)
    scores = pca.fit_transform(returns_demeaned)
    loadings = pca.components_.T
    factor_cov = np.cov(scores, rowvar=False)
    cov = loadings @ factor_cov @ loadings.T
    resid = returns_demeaned - scores @ loadings.T
    cov += np.diag(resid.var(axis=0, ddof=0))
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
