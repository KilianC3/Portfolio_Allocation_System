import numpy as np
import pandas as pd

from analytics import sharpe, alpha_beta, sortino
from config import MIN_ALLOC, MAX_ALLOC
from logger import get_logger
_log = get_logger("alloc")
def _dd(series):
    curve=(1+series).cumprod()
    dd=curve/curve.cummax()-1
    return dd.tail(20).min()
def compute_weights(
    ret_df: pd.DataFrame,
    benchmark: pd.Series | None = None,
    target_vol: float = 0.10,
    lmb: float = 0.8,
) -> dict:
    """Compute dynamic portfolio weights using risk-adjusted metrics."""

    lookback = 60
    hist = ret_df.tail(lookback)
    sharpe_scores = hist.apply(sharpe)
    sortino_scores = hist.apply(sortino)
    score = (sharpe_scores + 0.5 * sortino_scores).clip(lower=0.0)

    if benchmark is not None:
        bench = benchmark.tail(lookback).reindex(hist.index).fillna(0)
        ab = hist.apply(lambda s: alpha_beta(s, bench), result_type="expand")
        ab.index = ["alpha", "beta"]
        alphas = ab.loc["alpha"].clip(lower=0.0)
        betas = ab.loc["beta"].abs()
        score += alphas
        score /= 1 + (betas - 1).abs()

    score = score.pow(lmb)
    if score.sum() == 0:
        score += 1
    w = score / score.sum()

    dd = hist.apply(_dd)
    w.loc[dd < -0.06] *= 0.5
    w /= w.sum()

    cov = hist.cov() * 252
    port_vol = float(np.sqrt(w @ cov @ w))
    k = min(1.5, target_vol / port_vol)
    w *= k
    w = w.clip(lower=MIN_ALLOC, upper=MAX_ALLOC)
    w /= w.sum()

    _log.info({"weights": w.to_dict(), "vol": port_vol, "scale": k})
    return w.to_dict()
