"""Position and portfolio exposure calculations."""

from __future__ import annotations

from typing import Dict


def gross_exposure(positions: Dict[str, float], prices: Dict[str, float]) -> float:
    """Compute gross exposure given positions and prices."""
    return float(sum(abs(qty) * prices.get(sym, 0.0) for sym, qty in positions.items()))


def net_exposure(positions: Dict[str, float], prices: Dict[str, float]) -> float:
    """Compute net exposure given positions and prices."""
    return float(sum(qty * prices.get(sym, 0.0) for sym, qty in positions.items()))

__all__ = ["gross_exposure", "net_exposure"]
