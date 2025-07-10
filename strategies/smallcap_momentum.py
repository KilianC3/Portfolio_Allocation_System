from __future__ import annotations

import datetime as dt
from typing import Dict

import pandas as pd
import yfinance as yf

from core.equity import EquityPortfolio


class SmallCapMomentum:
    """Hold small-cap stocks heading into momentum catalysts."""

    def __init__(self, events: Dict[str, dt.date]):
        self.events = events  # symbol -> event date
        self.book: Dict[str, tuple[pd.Timestamp, float]] = {}

    @staticmethod
    def is_biotech(sym: str) -> bool:
        """Return True if the ticker appears to be a biotech/biomedical company."""
        try:
            info = yf.Ticker(sym).info
        except Exception:
            return False
        sector = str(info.get("sector", "")).lower()
        industry = str(info.get("industry", "")).lower()
        return (
            "biotechnology" in industry
            or "biotechnology" in sector
            or "biomedical" in industry
        )

    def _latest_price(self, sym: str) -> float:
        df = yf.download(sym, period="1d", interval="1d", progress=False)["Close"]
        if df.empty:
            return float("nan")
        return float(df.iloc[-1])

    async def build(self, pf: EquityPortfolio) -> None:
        today = pd.Timestamp.today().normalize()
        # drop positions past catalyst, +50% gain, or 3 months
        to_remove = []
        for sym, (entry_date, entry_price) in self.book.items():
            price = self._latest_price(sym)
            if price != price:  # NaN
                continue
            if (
                today >= pd.Timestamp(self.events.get(sym, today))
                or price >= 1.5 * entry_price
                or (today - entry_date).days >= 90
            ):
                to_remove.append(sym)
        for sym in to_remove:
            self.book.pop(sym, None)

        # add new events within next 3 months
        cutoff = today + pd.Timedelta(days=90)
        for sym, ev_dt in self.events.items():
            if sym in self.book:
                continue
            if not self.is_biotech(sym):
                continue
            if today <= pd.Timestamp(ev_dt) <= cutoff:
                price = self._latest_price(sym)
                if price == price:
                    self.book[sym] = (today, price)

        if not self.book:
            return

        w = {sym: 1 / len(self.book) for sym in self.book}
        pf.set_weights(w)
        await pf.rebalance()
