"""Position based risk checks."""

from __future__ import annotations

from typing import Optional

from .circuit import CircuitBreaker
from ledger import MasterLedger


class PositionRisk:
    def __init__(self, ledger: MasterLedger, max_position: float = 1000.0):
        self.ledger = ledger
        self.max_position = max_position
        self.circuit = CircuitBreaker()

    async def check(self, pf_id: str, symbol: str, qty: float) -> None:
        free = await self.ledger.free_float(pf_id, symbol)
        if free + qty < 0:
            self.circuit.trip()
            raise ValueError("negative free float")
        cur = await self.ledger.current_position(pf_id, symbol)
        if abs(cur + qty) > self.max_position:
            self.circuit.trip()
            raise ValueError("position limit")
