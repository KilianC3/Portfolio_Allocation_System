from __future__ import annotations

import os
from typing import Dict

import requests
import pandas as pd
import numpy as np

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
START_DATE = "2015-01-01"

# Default series IDs from FRED
DEFAULT_SERIES = {
    "vix": "VIXCLS",
    "eurusd": "DEXUSEU",
    "irx": "DGS1MO",
    "fvx": "DGS5",
    "tnx": "DGS10",
    "tyx": "DGS30",
    "federal_funds_rate": "FEDFUNDS",
    "cpi": "CPIAUCSL",
    "unemployment_rate": "UNRATE",
    "real_gdp": "GDPC1",
    "industrial_production": "INDPRO",
    "consumer_sentiment": "UMCSENT",
}

DEFAULT_WEIGHTS = {
    "vix": 0.20,
    "eurusd": 0.05,
    "irx": 0.05,
    "fvx": 0.05,
    "tnx": 0.10,
    "tyx": 0.10,
    "federal_funds_rate": 0.10,
    "cpi": 0.10,
    "unemployment_rate": 0.10,
    "real_gdp": 0.05,
    "industrial_production": 0.05,
    "consumer_sentiment": 0.05,
}

_tot = sum(DEFAULT_WEIGHTS.values())
DEFAULT_WEIGHTS = {k: v / _tot for k, v in DEFAULT_WEIGHTS.items()}


def get_fred_series(series_id: str, api_key: str, start: str = START_DATE) -> pd.Series:
    """Fetch a FRED series and return a numeric pandas Series indexed by date."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    resp = requests.get(FRED_OBS_URL, params=params, timeout=10)
    data = resp.json().get("observations", [])
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].rename(series_id)


def compute_z_scores(df: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """Rolling z-score calculation."""
    rolling_mean = df.rolling(window).mean()
    rolling_std = df.rolling(window).std()
    return (df - rolling_mean) / rolling_std


def compute_cci(signals: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    """Compute the Crisis Composite Indicator (CCI)."""
    z = compute_z_scores(signals)
    z_pos = z.clip(lower=0)
    w = pd.Series(weights).reindex(signals.columns).fillna(0)
    return (z_pos * w).sum(axis=1).rename("CCI")


def latest_cci(api_key: str | None = None) -> float:
    """Return the most recent CCI value using default series and weights."""
    key = api_key or os.getenv("FRED_API_KEY", "")
    frames = []
    for sid in DEFAULT_SERIES.values():
        frames.append(get_fred_series(sid, key))
    df = pd.concat(frames, axis=1)
    df = df.ffill().dropna()
    cci = compute_cci(df, DEFAULT_WEIGHTS)
    return float(cci.iloc[-1])


def cci_scaling(cci: float) -> float:
    """Exposure scaling factor S(CCI)."""
    if cci < 1.0:
        return 1.0
    if cci < 2.0:
        return 1.0 - 0.3 * (cci - 1.0)
    fac = 0.7 - 0.4 * (cci - 2.0)
    return max(fac, 0.3)


def scale_weights(weights: Dict[str, float], cci: float) -> Dict[str, float]:
    """Scale allocations by the stress indicator."""
    s = cci_scaling(cci)
    return {k: v * s for k, v in weights.items()}


__all__ = [
    "get_fred_series",
    "compute_z_scores",
    "compute_cci",
    "latest_cci",
    "cci_scaling",
    "scale_weights",
]
