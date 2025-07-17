"""Small-cap portfolio construction helpers."""

from __future__ import annotations

import pandas as pd
import numpy as np

__all__ = [
    "build_sector_neutral_portfolio",
    "build_micro_small_composite_leaders",
]


def build_sector_neutral_portfolio(df: pd.DataFrame, top_n_per_sector: int = 2) -> dict[str, float]:
    """Construct a sector-neutral portfolio of small-cap stocks."""
    # Universe filter
    mask = (
        (df["market_cap"] >= 100_000_000)
        & (df["market_cap"] <= 2_000_000_000)
        & (df["avg_dollar_volume"] >= 5_000_000)
    )
    universe = df.loc[mask].copy()
    if universe.empty:
        return {}

    # Rank within sector by composite score
    universe["rank"] = universe.groupby("sector")["composite_score"].rank("first", ascending=False)
    picks = universe[universe["rank"] <= top_n_per_sector]
    if picks.empty:
        return {}

    weights = {}
    sectors = picks["sector"].unique()
    n_sectors = len(sectors)
    if n_sectors == 0:
        return {}

    sector_weight = 1.0 / n_sectors
    for sector, group in picks.groupby("sector"):
        n = len(group)
        if n == 0:
            continue
        w = sector_weight / n
        for sym in group["ticker"]:
            weights[sym] = w

    # Position cap at 5%
    for sym in list(weights):
        if weights[sym] > 0.05:
            weights[sym] = 0.05
    total = sum(weights.values())
    if total == 0:
        return {}
    weights = {k: v / total for k, v in weights.items()}

    # stub: call quarterly
    return weights


def build_micro_small_composite_leaders(df: pd.DataFrame) -> dict[str, float]:
    """Composite leaders strategy for micro/small caps."""
    mask = (
        (df["market_cap"] >= 100_000_000)
        & (df["market_cap"] <= 1_000_000_000)
        & (df["avg_dollar_volume"] >= 1_000_000)
    )
    uni = df.loc[mask].copy()
    if uni.empty:
        return {}

    # top 25% by composite score
    cutoff = uni["composite_score"].quantile(0.75)
    uni = uni[uni["composite_score"] >= cutoff]

    # fundamental and momentum filters
    uni = uni[(uni["free_cash_flow_ttm"] > 0) & (uni["ROE"] > 0) & (uni["return_3m"] > 0)]
    if uni.empty:
        return {}

    # raw weights
    raw = uni["composite_score"] / np.sqrt(uni["market_cap"])
    weights = raw / raw.sum()

    # cap at 4%
    weights = weights.clip(upper=0.04)
    weights = weights / weights.sum()

    # trim illiquid names
    spreads = uni["bid_ask_spread"]
    if any(spreads > 5):
        weights[spreads > 5] = 0
        weights = weights / weights.sum()

    # scale by volatility if needed
    port_vol = float((uni["vol_30d"] * weights).sum())
    if port_vol > 18:
        weights *= 15 / 18
        weights = weights / weights.sum()

    # stub for trailing stop-loss logic

    return weights.to_dict()
