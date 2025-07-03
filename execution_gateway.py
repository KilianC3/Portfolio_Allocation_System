"""Execution gateway using strategy pattern."""

from __future__ import annotations

import uuid
from typing import Optional

from alpaca_trade_api import REST

from logger import get_logger
from config import ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL
from database import trade_coll

_log = get_logger("exec_gateway")

class ExecutionGateway:
    """Abstract execution gateway interface."""

    def order_to_pct(self, symbol: str, pct: float, pf_id: Optional[str] = None):
        raise NotImplementedError


class AlpacaGateway(ExecutionGateway):
    """Alpaca REST implementation."""

    MAX_NOTIONAL = 25_000

    def __init__(self) -> None:
        self.api = REST(
            ALPACA_API_KEY,
            ALPACA_API_SECRET,
            ALPACA_BASE_URL,
            api_version="v2",
        )

    def _pv(self) -> float:
        return float(self.api.get_account().portfolio_value)

    def _price(self, symbol: str) -> float:
        return float(self.api.get_latest_trade(symbol).price)

    def _risk(self, diff: float) -> None:
        if abs(diff) > self.MAX_NOTIONAL:
            raise ValueError("notional guard")

    def _pf_position_value(self, symbol: str, pf_id: str) -> float:
        qty = 0.0
        for d in trade_coll.find({"portfolio_id": pf_id, "symbol": symbol}):
            q = float(d.get("qty", 0))
            if d.get("side") == "sell":
                qty -= q
            else:
                qty += q
        return qty * self._price(symbol)

    def order_to_pct(self, symbol: str, pct: float, pf_id: Optional[str] = None):
        pv = self._pv()
        tgt = pv * pct
        if pf_id:
            cur = self._pf_position_value(symbol, pf_id)
        else:
            try:
                cur = float(self.api.get_position(symbol).market_value)
            except Exception:
                cur = 0.0
        diff = tgt - cur
        self._risk(diff)
        if abs(diff) / pv < 0.0003:
            return None
        qty = round(diff / self._price(symbol), 3)
        if qty == 0:
            return None
        side = "buy" if qty > 0 else "sell"
        _log.info(f"{side} {abs(qty)} {symbol}")
        client_id = f"{pf_id}-{uuid.uuid4().hex[:8]}" if pf_id else None
        kwargs = {"client_order_id": client_id} if client_id else {}
        return self.api.submit_order(symbol, abs(qty), side, "market", "day", **kwargs)

__all__ = ["ExecutionGateway", "AlpacaGateway"]
