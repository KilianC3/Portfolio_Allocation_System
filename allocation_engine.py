"""Enhanced portfolio allocation engine."""

from __future__ import annotations

from typing import Mapping, Optional, Literal

import numpy as np
import pandas as pd

from analytics.covariance import estimate_covariance
from analytics.blacklitterman import market_implied_returns, black_litterman_posterior
from analytics.robust import minmax_portfolio
from risk.corr_regime import correlation_regime

from config import MAX_ALLOC, MIN_ALLOC
from database import db, alloc_log_coll
from logger import get_logger

_log = get_logger("alloc")


def _sharpe(r: pd.Series) -> float:
    """Annualised Sharpe ratio."""
    std = r.std(ddof=0)
    if std == 0:
        return 0.0
    return float(r.mean() / std * np.sqrt(252))


def _sortino(r: pd.Series) -> float:
    """Annualised Sortino ratio."""
    downside = r[r < 0].std(ddof=0)
    if downside == 0:
        return 0.0
    return float(r.mean() / downside * np.sqrt(252))


def _alpha_beta(r: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    """Annualised alpha and beta relative to a benchmark."""
    benchmark = benchmark.reindex(r.index).fillna(0)
    cov = np.cov(r, benchmark, ddof=0)
    beta = 0.0 if cov[1, 1] == 0 else cov[0, 1] / cov[1, 1]
    alpha = (r.mean() - beta * benchmark.mean()) * 252
    return float(alpha), float(beta)


def _dd(series: pd.Series) -> float:
    """Rolling 20-day drawdown."""
    curve = (1 + series).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.tail(20).min())


def _risk_parity(w: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Return weights scaled so risk contributions are equal."""
    arr = w.to_numpy()
    cov_m = cov.to_numpy()
    n = len(arr)
    for _ in range(100):
        rc = arr * (cov_m @ arr)
        total = float(np.sqrt(arr @ cov_m @ arr))
        target = total / n
        diff = rc - target
        if np.all(np.abs(diff) < 1e-6):
            break
        arr *= target / rc
        arr /= arr.sum()
    return pd.Series(arr, index=w.index)


def _log_to_db(table: pd.DataFrame) -> None:
    """Persist scoring table for audit; ignore failures."""
    try:
        coll = alloc_log_coll if alloc_log_coll else db["alloc_log"]
        coll.insert_one(
            table.reset_index().rename(columns={"index": "symbol"}).to_dict()
        )
    except Exception as exc:  # pragma: no cover - logging should not fail tests
        _log.warning({"db_error": str(exc)})


def compute_weights(
    ret_df: pd.DataFrame,
    benchmark: Optional[pd.Series] = None,
    target_vol: float = 0.10,
    lam: float = 0.97,
    w_prev: Optional[Mapping[str, float]] = None,
    lambda_fee: float = 0.0,
    drift_band: float = 0.03,
    score_power: float = 1.0,
    sector_map: Optional[Mapping[str, str]] = None,
    sector_caps: Optional[Mapping[str, float]] = None,
    signals: Optional[pd.Series] = None,
    market_caps: Optional[pd.Series] = None,
    cov_method: Literal["ledoit", "pca"] = "ledoit",
    robust: bool = False,
) -> dict[str, float]:
    """Compute dynamic portfolio weights.

    Parameters
    ----------
    ret_df: pd.DataFrame
        Daily returns for each asset.
    benchmark: pd.Series | None
        Benchmark returns for alpha/beta metrics.
    target_vol: float
        Desired annualised portfolio volatility.
    lam: float
        Exponential decay factor for weighting returns.
    w_prev: Mapping[str, float] | None
        Previous portfolio weights.
    lambda_fee: float
        Turnover penalty coefficient.
    drift_band: float
        No-trade band around previous weights.
    score_power: float
        Exponent applied to the combined score before normalising.
    sector_map: Mapping[str, str] | None
        Map from symbol to sector name.
    sector_caps: Mapping[str, float] | None
        Maximum weight per sector.
    signals: pd.Series | None
        Expected return views for Black-Litterman adjustment.
    market_caps: pd.Series | None
        Market capitalisation weights for equilibrium returns.
    cov_method: str
        Covariance estimation method ("ledoit" or "pca").
    robust: bool
        Use min-max optimisation to guard against covariance uncertainty.

    Returns
    -------
    dict[str, float]
        New portfolio weights normalised to sum to one.
    """

    lookback = 120
    hist = ret_df.tail(lookback)
    alpha = 1 - lam

    # Exponentially weighted statistics
    mean = hist.ewm(alpha=alpha, adjust=False).mean().iloc[-1]
    vol = hist.ewm(alpha=alpha, adjust=False).std(bias=False).iloc[-1]
    downside = (
        hist.clip(upper=0).ewm(alpha=alpha, adjust=False).std(bias=False).iloc[-1]
    )

    sharpe_scores = (mean / vol.replace(0, np.nan)).fillna(0) * np.sqrt(252)
    sortino_scores = (mean / downside.replace(0, np.nan)).fillna(0) * np.sqrt(252)
    score = (sharpe_scores + 0.5 * sortino_scores).clip(lower=0.0)

    ab = None
    if benchmark is not None:
        bench = benchmark.tail(lookback).reindex(hist.index).fillna(0)
        ab = hist.apply(lambda s: _alpha_beta(s, bench), result_type="expand")
        ab.index = ["alpha", "beta"]
        alphas = ab.loc["alpha"].clip(lower=0.0)
        betas = ab.loc["beta"].abs()
        score += alphas
        score /= 1 + (betas - 1).abs()

    score = score.pow(score_power)
    if score.sum() == 0:
        score += 1
    w = score / score.sum()

    dd = hist.apply(_dd)
    thresh = dd.quantile(0.25)
    w.loc[dd <= thresh] *= 0.5
    w /= w.sum()

    cov = estimate_covariance(hist, method=cov_method)

    if signals is not None and market_caps is not None:
        market_caps = market_caps.reindex(hist.columns).fillna(0)
        market_weights = market_caps / market_caps.sum()
        pi = market_implied_returns(cov, market_weights)
        P = pd.DataFrame(
            np.eye(len(signals)), index=signals.index, columns=signals.index
        )
        Q = signals.reindex(signals.index)
        tau_adj = 0.05 * (1 + signals.std())
        bl_mu = black_litterman_posterior(cov, pi, P, Q, tau=tau_adj)
        score = bl_mu.clip(lower=0.0)
        if score.sum() == 0:
            score += 1
        w = score / score.sum()

    w = _risk_parity(w, cov)
    if robust:
        w = minmax_portfolio(score, cov, gamma=2.0)

    regime = correlation_regime(hist)
    if regime == "high":
        w *= 0.5
        w /= w.sum()

    if w_prev is not None and lambda_fee > 0:
        prev = pd.Series(w_prev).reindex(w.index).fillna(0)
        penalty = lambda_fee * (w - prev).pow(2)
        w_adj = (w - penalty).clip(lower=0)
        if w_adj.sum() > 0:
            w = w_adj / w_adj.sum()

    port_vol = float(np.sqrt(w @ cov @ w))
    k = min(1.5, target_vol / port_vol)
    w *= k

    w = w.clip(lower=MIN_ALLOC, upper=MAX_ALLOC)
    w /= w.sum()

    if sector_map and sector_caps:
        for sector, cap in sector_caps.items():
            assets = [sym for sym, sec in sector_map.items() if sec == sector]
            sec_weight = w.reindex(assets).sum()
            if sec_weight > cap and sec_weight > 0:
                scale = cap / sec_weight
                w_sector = w.loc[assets] * scale
                others = w.drop(assets)
                other_total = others.sum()
                if other_total > 0:
                    others = others / other_total * (1 - w_sector.sum())
                w = pd.concat([w_sector, others]).reindex(w.index)
        w /= w.sum()

    if w_prev is not None:
        prev = pd.Series(w_prev).reindex(w.index).fillna(0)
        if ((w - prev).abs() <= drift_band).all():
            w = prev

    assert abs(w.sum() - 1.0) <= 1e-6, "weights do not sum to one"
    if np.sqrt(float(w @ cov @ w)) > target_vol * 1.1:
        raise ValueError("volatility target unattainable")

    table = pd.DataFrame(
        {
            "sharpe": sharpe_scores,
            "sortino": sortino_scores,
            "drawdown": dd,
            "weight": w,
        }
    )
    if ab is not None:
        table.loc["alpha"] = ab.loc["alpha"]
        table.loc["beta"] = ab.loc["beta"]
    _log_to_db(table.T)

    _log.info({"weights": w.to_dict(), "vol": port_vol, "scale": k})
    return w.to_dict()
