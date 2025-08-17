"""Utility functions for portfolio analytics."""

import math
import functools
import os
import datetime as dt
from threading import Lock
from typing import Mapping, Optional, Any

from database import position_coll

import numpy as np
import pandas as pd
import yfinance as yf


_TREASURY_CACHE: dict[str, Any] = {
    "rate": 0.0,
    "timestamp": dt.datetime.fromtimestamp(0),
}
_CACHE_LOCK = Lock()


def get_treasury_rate(force: bool = False) -> float:
    """Return the 3M treasury rate with simple caching.

    The rate is fetched via yfinance's ``^IRX`` ticker and cached alongside
    a timestamp. Subsequent calls reuse the cached value until ``TREASURY_RATE_TTL``
    seconds have elapsed unless ``force`` is ``True``.
    """
    ttl = int(os.getenv("TREASURY_RATE_TTL", 86400))
    now = dt.datetime.utcnow()
    with _CACHE_LOCK:
        age = (now - _TREASURY_CACHE["timestamp"]).total_seconds()
        if not force and age < ttl and _TREASURY_CACHE["rate"]:
            return float(_TREASURY_CACHE["rate"])
        try:
            rate = (
                float(yf.Ticker("^IRX").history(period="1d")["Close"].iloc[-1]) / 100.0
            )
        except Exception:
            rate = float(_TREASURY_CACHE["rate"])
        _TREASURY_CACHE.update({"rate": rate, "timestamp": now})
        return float(rate)


def get_treasury_timestamp() -> dt.datetime:
    """Return the timestamp associated with the cached treasury rate."""
    with _CACHE_LOCK:
        return _TREASURY_CACHE["timestamp"]


def lambda_from_half_life(h: int) -> float:
    """Return the exponential decay factor for a given half-life ``h``."""
    return 1 - 2 ** (-1 / h)


def sharpe(r: pd.Series, rf: float = 0.0) -> float:
    """Annualised Sharpe ratio of a returns series."""
    std = r.std(ddof=0)
    if std == 0:
        return 0.0
    return (r.mean() - rf) / std * math.sqrt(252)


def var_cvar(r: pd.Series, level: float = 0.95) -> tuple[float, float]:
    """Return VaR and CVaR for a return series."""
    var = np.quantile(r, 1 - level)
    cvar = r[r <= var].mean()
    return float(var), float(cvar)


def value_at_risk(r: pd.Series, level: float = 0.95) -> float:
    """Wrapper returning only the Value at Risk for convenience."""
    return float(np.quantile(r, 1 - level))


def conditional_value_at_risk(r: pd.Series, level: float = 0.95) -> float:
    """Return the Conditional VaR (expected shortfall) of ``r``."""
    var = value_at_risk(r, level)
    return float(r[r <= var].mean())


def drawdown_series(r: pd.Series) -> pd.Series:
    """Return the drawdown series derived from ``r``."""
    curve = (1 + r).cumprod()
    return curve / curve.cummax() - 1


def alpha_beta(r: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    """Annualised alpha and beta relative to a benchmark."""
    bench = benchmark.reindex(r.index).fillna(0)
    cov = np.cov(r, bench, ddof=0)
    beta = 0.0 if cov[1, 1] == 0 else cov[0, 1] / cov[1, 1]
    alpha = (r.mean() - beta * bench.mean()) * 252
    return float(alpha), float(beta)


def fama_french_params(
    r: pd.Series,
    mkt: pd.Series,
    smb: pd.Series,
    hml: pd.Series,
    rf: float = 0.0,
) -> tuple[float, float, float, float]:
    """Return alpha and factor betas for the Fama-French 3-factor model."""
    df = pd.concat([r, mkt, smb, hml], axis=1, join="inner").dropna()
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0
    y = df.iloc[:, 0] - rf
    X = df.iloc[:, 1:]
    X.insert(0, "const", 1.0)
    params, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    alpha = params[0] * 252
    beta_mkt, beta_smb, beta_hml = params[1:]
    return float(alpha), float(beta_mkt), float(beta_smb), float(beta_hml)


def get_ten_year_treasury_rate() -> float:
    """Fetch the latest 10 Year Treasury yield as a decimal."""
    try:
        data = yf.Ticker("^TNX").history(period="1d")
        return float(data["Close"].iloc[-1] / 100)
    except Exception:
        return 0.0


def max_drawdown(r: pd.Series) -> float:
    """Maximum drawdown of a returns series."""
    curve = (1 + r).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())


def period_return(r: pd.Series, days: int) -> float:
    """Cumulative return over the last ``days`` observations."""
    segment = r.dropna().iloc[-days:]
    if segment.empty:
        return 0.0
    return float((segment + 1).prod() - 1)


def sortino(r: pd.Series, rf: float = 0.0) -> float:
    """Annualised Sortino ratio using downside deviation."""
    downside = r[r < 0].std(ddof=0)
    if downside == 0:
        return 0.0
    return (r.mean() - rf) / downside * math.sqrt(252)


def weekly_volatility(r: pd.Series) -> float:
    """Standard deviation over the last 5 sessions."""
    return float(r.dropna().tail(5).std(ddof=0))


def weekly_sortino(r: pd.Series, rf: float = 0.0) -> float:
    """Sortino ratio over the last 5 sessions without annualisation."""
    seg = r.dropna().tail(5)
    downside = seg[seg < 0].std(ddof=0)
    if downside == 0:
        return 0.0
    return float((seg.mean() - rf) / downside)


def average_true_range(r: pd.Series, window: int = 14) -> float:
    """Approximate ATR using absolute returns as the true range."""
    return float(r.abs().rolling(window).mean().iloc[-1])


def rsi(r: pd.Series, window: int = 14) -> float:
    """Relative Strength Index computed from returns."""
    delta = r.fillna(0)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window).mean().iloc[-1]
    avg_loss = loss.rolling(window).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def cumulative_return(r: pd.Series) -> float:
    """Total cumulative return for the period."""
    return float((1 + r).prod() - 1)


def tracking_error(r: pd.Series, benchmark: pd.Series) -> float:
    """Annualised tracking error of a portfolio versus a benchmark."""
    diff = r - benchmark.reindex(r.index).fillna(0)
    return diff.std(ddof=0) * math.sqrt(252)


def information_ratio(r: pd.Series, benchmark: pd.Series) -> float:
    """Information ratio relative to a benchmark."""
    te = tracking_error(r, benchmark)
    if te == 0:
        return 0.0
    return (r.mean() - benchmark.reindex(r.index).fillna(0).mean()) / te


def portfolio_metrics(
    r: pd.Series,
    factors: Optional[pd.DataFrame] = None,
    rf: float = 0.0,
) -> dict:
    """Compute a comprehensive set of portfolio metrics.

    ``factors`` should contain a ``mkt`` column for the market return and
    optional ``smb`` and ``hml`` columns for size and value factors.
    """
    metrics = {
        "ret_1d": period_return(r, 1),
        "ret_7d": period_return(r, 7),
        "ret_30d": period_return(r, 30),
        "ret_3m": period_return(r, 63),
        "ret_6m": period_return(r, 126),
        "ret_1y": period_return(r, 252),
        "ret_2y": period_return(r, 504),
        "cumulative_return": cumulative_return(r),
        "sharpe": sharpe(r, rf),
        "sortino": sortino(r, rf),
        "weekly_vol": weekly_volatility(r),
        "weekly_sortino": weekly_sortino(r, rf),
        "max_drawdown": max_drawdown(r),
        "annual_vol": r.std(ddof=0) * math.sqrt(252),
        "annual_std": r.std(ddof=0) * math.sqrt(252),
        "win_rate": float((r > 0).mean()),
        "avg_win": float(r[r > 0].mean() if (r > 0).any() else 0.0),
        "avg_loss": float(r[r < 0].mean() if (r < 0).any() else 0.0),
    }
    days = len(r.dropna())
    if days:
        metrics["cagr"] = (1 + cumulative_return(r)) ** (252 / days) - 1
    else:
        metrics["cagr"] = 0.0
    var, cvar = var_cvar(r)
    metrics["var"] = var
    metrics["cvar"] = cvar

    if factors is not None and not factors.empty:
        mkt = factors.get("mkt")
        if mkt is not None:
            smb = factors.get("smb")
            hml = factors.get("hml")
            if smb is not None and hml is not None:
                a, b_mkt, b_smb, b_hml = fama_french_params(r, mkt, smb, hml, rf)
                metrics["alpha"] = a
                metrics["beta"] = b_mkt
                metrics["beta_smb"] = b_smb
                metrics["beta_hml"] = b_hml
                metrics["tracking_error"] = tracking_error(r, mkt)
                metrics["information_ratio"] = information_ratio(r, mkt)
                metrics["treynor_ratio"] = (
                    0.0 if b_mkt == 0 else (r.mean() - rf) / b_mkt
                )
                market_ret = mkt.mean() * 252
                smb_ret = smb.mean() * 252
                hml_ret = hml.mean() * 252
                metrics["ff_expected_return"] = (
                    rf + b_mkt * (market_ret - rf) + b_smb * smb_ret + b_hml * hml_ret
                )
            else:
                a, b = alpha_beta(r, mkt)
                metrics["alpha"] = a
                metrics["beta"] = b
                metrics["tracking_error"] = tracking_error(r, mkt)
                metrics["information_ratio"] = information_ratio(r, mkt)
                metrics["treynor_ratio"] = 0.0 if b == 0 else (r.mean() - rf) / b
                market_ret = mkt.mean() * 252
                metrics["ff_expected_return"] = rf + b * (market_ret - rf)

    metrics["atr_14d"] = average_true_range(r)
    metrics["rsi_14d"] = rsi(r)
    return metrics


def aggregate_daily_returns_exposure(
    pf_id: str,
    returns: pd.Series,
    exposure: Optional[pd.Series],
    coll,
) -> None:
    """Aggregate daily returns and exposure and persist to ``coll``.

    Parameters
    ----------
    pf_id: str
        Portfolio identifier used as ``portfolio_id`` in the collection.
    returns: pd.Series
        Daily return series indexed by date.
    exposure: Optional[pd.Series]
        Optional exposure series aligned with ``returns``.
    coll: Collection
        MongoDB collection-like object with ``update_one`` method.
    """

    df = pd.DataFrame({"ret": returns}).dropna()
    if exposure is not None:
        df["exposure"] = exposure.reindex(df.index).fillna(0)
    records: list[dict[str, Any]] = []
    for date, row in df.iterrows():
        rec: dict[str, Any] = {
            "portfolio_id": pf_id,
            "date": pd.to_datetime(date).date(),
            "ret": float(row["ret"]),
        }
        if "exposure" in row:
            rec["exposure"] = float(row["exposure"])
        records.append(rec)
    if records:
        coll.insert_many(records)


def portfolio_correlations(ret_df: pd.DataFrame) -> pd.DataFrame:
    """Pairwise correlation matrix of portfolio returns."""
    return ret_df.corr().fillna(0)


@functools.lru_cache(maxsize=1024)
def ticker_sector(sym: str) -> str:
    """Return the sector for a ticker via yfinance; "Other" on failure."""
    try:
        info = yf.Ticker(sym).info
    except Exception:
        return "Other"
    sector = info.get("sector") or info.get("industry") or "Other"
    return str(sector)


def sector_exposures(weights: Mapping[str, float]) -> dict[str, float]:
    """Aggregate weights by sector."""
    totals: dict[str, float] = {}
    for sym, w in weights.items():
        sec = ticker_sector(sym)
        totals[sec] = totals.get(sec, 0.0) + float(w)
    return totals


def unrealized_pnl(pf_id: str, prices: Mapping[str, float]) -> dict[str, float]:
    """Return unrealised PnL per symbol and in total for ``pf_id``.

    Parameters
    ----------
    pf_id: str
        Portfolio identifier.
    prices: Mapping[str, float]
        Latest price for each symbol.
    """

    totals: dict[str, float] = {}
    total = 0.0
    for d in position_coll.find({"portfolio_id": pf_id}):
        sym = d["symbol"]
        qty = float(d.get("qty", 0.0))
        cost = float(d.get("cost_basis", 0.0))
        price = float(prices.get(sym, 0.0))
        pnl = qty * price - cost
        totals[sym] = pnl
        total += pnl
    totals["total"] = total
    return totals


__all__ = [
    "sharpe",
    "var_cvar",
    "alpha_beta",
    "max_drawdown",
    "sortino",
    "weekly_volatility",
    "weekly_sortino",
    "average_true_range",
    "rsi",
    "cumulative_return",
    "period_return",
    "tracking_error",
    "information_ratio",
    "portfolio_metrics",
    "aggregate_daily_returns_exposure",
    "fama_french_params",
    "portfolio_correlations",
    "ticker_sector",
    "sector_exposures",
    "unrealized_pnl",
    "lambda_from_half_life",
    "get_treasury_rate",
]
