"""Equity portfolio implementation."""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from typing import Any, Dict

from database import trade_coll, pf_coll, weight_coll, position_coll
from infra.github_backup import backup_records
from execution.gateway import ExecutionGateway
from ledger import MasterLedger
from risk import PositionRisk
from service.logger import get_logger

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

    def set_weights(
        self,
        weights: Dict[str, float],
        strategy: str | None = None,
        risk_target: float | None = None,
        allowed_strategies: list[str] | None = None,
    ) -> None:
        """Assign target weights ensuring normalisation and validation.

        Optional ``strategy`` and ``risk_target`` parameters are persisted so
        clients can inspect or adjust the allocation method and risk level used
        for this portfolio. ``allowed_strategies`` restricts the set of
        allocation methods that may be assigned to the portfolio.
        """

        if any(w < 0 for w in weights.values()):
            raise ValueError("weights must be non-negative")

        symbols = getattr(self.gateway, "symbols", None)
        if symbols is not None:
            unknown = set(weights) - set(symbols)
            if unknown:
                raise ValueError(f"Unknown symbols: {unknown}")

        total = sum(weights.values())
        if total <= 0:
            raise ValueError("total weight must be positive")

        if total > 1:
            scaled = {s: w / total for s, w in weights.items()}
            cash = 0.0
        else:
            scaled = dict(weights)
            cash = 1 - total

        self.weights = scaled
        persisted = dict(scaled)
        if cash > 0:
            persisted["cash"] = cash
        update_doc = {"weights": persisted}

        if allowed_strategies is not None:
            self.allowed_strategies = allowed_strategies
            update_doc["allowed_strategies"] = allowed_strategies

        allowed = allowed_strategies or getattr(self, "allowed_strategies", None)
        if strategy is not None:
            if allowed and strategy not in allowed:
                raise ValueError(f"strategy {strategy} not allowed")
            self.strategy = strategy
            update_doc["strategy"] = strategy

        if risk_target is not None:
            self.risk_target = risk_target
            update_doc["risk_target"] = risk_target

        pf_coll.update_one({"_id": self.id}, {"$set": update_doc}, upsert=True)
        try:
            doc = {
                "portfolio_id": self.id,
                "date": dt.date.today(),
                "weights": persisted,
            }
            weight_coll.update_one(
                {"portfolio_id": self.id, "date": dt.date.today()},
                {"$set": {"weights": persisted}},
                upsert=True,
            )
            backup_records("weight_history", [doc])
        except Exception:
            pass
        _log.info({"set": persisted, "pf": self.name})

    def _log_trade(self, order: Any) -> None:
        qty = float(order.qty)
        price = float(getattr(order, "filled_avg_price", 0.0))
        side = order.side
        signed_qty = -qty if side == "sell" else qty

        prev = (
            position_coll.find_one({"portfolio_id": self.id, "symbol": order.symbol})
            or {}
        )
        prev_qty = float(prev.get("qty", 0.0))
        prev_cost = float(prev.get("cost_basis", 0.0))
        prev_realized = float(prev.get("realized_pnl", 0.0))

        if signed_qty >= 0:
            new_qty = prev_qty + signed_qty
            new_cost = prev_cost + signed_qty * price
            realized = prev_realized
        else:
            avg_cost = 0.0 if prev_qty == 0 else prev_cost / prev_qty
            realized_trade = (-signed_qty) * (price - avg_cost)
            realized = prev_realized + realized_trade
            new_qty = prev_qty + signed_qty
            new_cost = avg_cost * new_qty

        position_coll.update_one(
            {"portfolio_id": self.id, "symbol": order.symbol},
            {
                "$set": {
                    "qty": new_qty,
                    "cost_basis": new_cost,
                    "realized_pnl": realized,
                }
            },
            upsert=True,
        )

        trade_coll.insert_one(
            {
                "portfolio_id": self.id,
                "timestamp": dt.datetime.now(dt.timezone.utc),
                "symbol": order.symbol,
                "side": side,
                "qty": qty,
                "price": price,
                "cost_basis": new_cost,
                "realized_pnl": realized,
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
        docs = list(position_coll.find({"portfolio_id": self.id}))
        return {d["symbol"]: float(d.get("qty", 0.0)) for d in docs}


__all__ = ["EquityPortfolio"]
