import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from sklearn.decomposition import PCA

from analytics import covariance


def ledoit_wolf_cov_python(returns: pd.DataFrame) -> pd.DataFrame:
    lw = LedoitWolf().fit(returns)
    return pd.DataFrame(lw.covariance_, index=returns.columns, columns=returns.columns)


def pca_factor_cov_python(returns: pd.DataFrame, n_components: int = 5) -> pd.DataFrame:
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


def test_ledoit_wolf_rust_matches_python():
    rng = np.random.default_rng(0)
    returns = pd.DataFrame(rng.normal(size=(500, 20)), columns=[f"A{i}" for i in range(20)])
    expected = ledoit_wolf_cov_python(returns)
    result = covariance.ledoit_wolf_cov(returns)
    assert np.allclose(result.values, expected.values)


def test_pca_factor_cov_rust_matches_python():
    rng = np.random.default_rng(1)
    returns = pd.DataFrame(rng.normal(size=(500, 20)), columns=[f"A{i}" for i in range(20)])
    expected = pca_factor_cov_python(returns)
    result = covariance.pca_factor_cov(returns)
    assert np.allclose(result.values, expected.values, atol=1e-2)
