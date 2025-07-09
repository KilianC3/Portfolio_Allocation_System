"""Equity portfolio implementation."""

from __future__ import annotations

import datetime as dt
import uuid
import math
from types import SimpleNamespace
from typing import Any, Dict

from database import trade_coll, pf_coll
from execution.gateway import ExecutionGateway
from ledger import MasterLedger
from risk import PositionRisk
from logger import get_logger

from .portfolio import Portfolio

_log = get_logger("equity_portfolio")


class EquityPortfolio(Portfolio):
    """Concrete portfolio for equities."""

    def __init__(
        self,
        name: str,
        gateway: ExecutionGateway,
        pf_id: str | None = None,
        ledger: MasterLedger | None = None,
    ):
        super().__init__(name, gateway)
        self.id = pf_id or str(uuid.uuid4())
        self.ledger = ledger
        self.risk = PositionRisk(self.ledger) if self.ledger else None
        pf_coll.update_one({"_id": self.id}, {"$set": {"name": self.name}}, upsert=True)

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Assign target weights without enforcing normalization."""
        self.weights = weights
        pf_coll.update_one(
            {"_id": self.id}, {"$set": {"weights": weights}}, upsert=True
        )
        _log.info({"set": weights, "pf": self.name})

    def _log_trade(self, order: Any) -> None:
        trade_coll.insert_one(
            {
                "portfolio_id": self.id,
                "timestamp": dt.datetime.now(dt.timezone.utc),
                "symbol": order.symbol,
                "side": order.side,
                "qty": float(order.qty),
                "price": float(getattr(order, "filled_avg_price", 0.0)),
            }
        )

    async def rebalance(self) -> None:
        current = self.positions()
        all_syms = set(current) | set(self.weights)
        for sym in all_syms:
            tgt = self.weights.get(sym, 0.0)
            order = await self.gateway.order_to_pct(
                sym, tgt, self.id, self.ledger, self.risk
            )
            if order:
                self._log_trade(
                    SimpleNamespace(**order) if isinstance(order, dict) else order
                )

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
