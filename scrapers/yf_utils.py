"""Helpers for normalising yfinance download columns."""

from __future__ import annotations

from typing import Tuple, Optional

import pandas as pd


def extract_close_volume(
    raw: pd.DataFrame | pd.Series | None,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Return close and volume frames from a raw yfinance download.

    Handles the many shapes returned by ``yf.download`` including single and
    multi-index columns.  ``raw`` may be a ``DataFrame`` or ``Series`` and may
    be ``None`` for network failures.  A ``None`` volume frame indicates the
    download did not contain volume information.
    """
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return pd.DataFrame(), None
    if isinstance(raw, pd.Series):
        return raw.to_frame(), None
    df = raw
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = df.columns.get_level_values(0)
        lvl1 = df.columns.get_level_values(1)
        if "Close" in lvl0:
            closes = df.xs("Close", level=0, axis=1)
            vols = df.xs("Volume", level=0, axis=1) if "Volume" in lvl0 else None
        elif "Close" in lvl1:
            closes = df.xs("Close", level=1, axis=1)
            vols = df.xs("Volume", level=1, axis=1) if "Volume" in lvl1 else None
        elif "Adj Close" in lvl1:
            closes = df.xs("Adj Close", level=1, axis=1)
            vols = df.xs("Volume", level=1, axis=1) if "Volume" in lvl1 else None
        else:
            closes = pd.DataFrame()
            vols = None
    else:
        closes = df.get("Close", pd.DataFrame())
        vols = df.get("Volume") if "Volume" in df.columns else None
    if isinstance(closes, pd.Series):
        closes = closes.to_frame()
    if vols is not None and isinstance(vols, pd.Series):
        vols = vols.to_frame()
    return closes, vols


__all__ = ["extract_close_volume"]
