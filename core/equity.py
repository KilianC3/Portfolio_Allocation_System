"""Equity portfolio implementation."""

from __future__ import annotations

import datetime as dt
import uuid
import math
from typing import Dict

from database import trade_coll, pf_coll
from execution_gateway import ExecutionGateway
from logger import get_logger

from .portfolio import Portfolio

_log = get_logger("equity_portfolio")

class EquityPortfolio(Portfolio):
    """Concrete portfolio for equities."""

    def __init__(self, name: str, gateway: ExecutionGateway, pf_id: str | None = None):
        super().__init__(name, gateway)
        self.id = pf_id or str(uuid.uuid4())
        pf_coll.update_one({"_id": self.id}, {"$set": {"name": self.name}}, upsert=True)

    def set_weights(self, weights: Dict[str, float]) -> None:
        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-4):
            raise ValueError("weights must sum to 1")
        self.weights = weights
        pf_coll.update_one({"_id": self.id}, {"$set": {"weights": weights}}, upsert=True)
        _log.info({"set": weights, "pf": self.name})

    def _log_trade(self, order: object) -> None:
        trade_coll.insert_one({
            "portfolio_id": self.id,
            "timestamp": dt.datetime.utcnow(),
            "symbol": order.symbol,
            "side": order.side,
            "qty": float(order.qty),
            "price": float(getattr(order, "filled_avg_price", 0.0)),
        })

    def rebalance(self) -> None:
        current = self.positions()
        all_syms = set(current) | set(self.weights)
        for sym in all_syms:
            tgt = self.weights.get(sym, 0.0)
            order = self.gateway.order_to_pct(sym, tgt, self.id)
            if order:
                self._log_trade(order)

    def positions(self) -> Dict[str, float]:
        docs = list(trade_coll.find({"portfolio_id": self.id}))
        pos: Dict[str, float] = {}
        for d in docs:
            qty = float(d.get("qty", 0))
            if d.get("side") == "sell":
                qty *= -1
            pos[d["symbol"]] = pos.get(d["symbol"], 0.0) + qty
        return pos

__all__ = ["EquityPortfolio"]
