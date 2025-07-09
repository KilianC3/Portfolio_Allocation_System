from __future__ import annotations

import pandas as pd

from core.equity import EquityPortfolio
from database import contracts_coll


class GovContractsMomentum:
    """Own firms with large new federal contracts."""

    def __init__(self, threshold: float = 50_000_000) -> None:
        self.threshold = threshold

    def _select(self) -> pd.Index:
        docs = list(contracts_coll.find())
        if not docs:
            return pd.Index([])
        df = pd.DataFrame(docs)
        df["value"] = (
            df["value"].str.replace("$", "").str.replace(",", "").astype(float)
        )
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "value"])
        cutoff = df["date"].max() - pd.Timedelta(days=30)
        recent = df[df["date"] >= cutoff]
        agg = recent.groupby("ticker")["value"].sum()
        return agg[agg >= self.threshold].index

    async def build(self, pf: EquityPortfolio) -> None:
        tickers = self._select()
        if tickers.empty:
            return
        w = {sym: 1 / len(tickers) for sym in tickers}
        pf.set_weights(w)
        await pf.rebalance()
