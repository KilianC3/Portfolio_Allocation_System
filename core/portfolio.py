"""Abstract portfolio definitions and utilities."""

from __future__ import annotations

import abc
from typing import Dict

from service.logger import get_logger
from execution.gateway import ExecutionGateway

_log = get_logger("portfolio")


class Portfolio(abc.ABC):
    """Abstract base class for portfolios."""

    def __init__(self, name: str, gateway: ExecutionGateway):
        self.name = name
        self.gateway = gateway
        self.weights: Dict[str, float] = {}

    @abc.abstractmethod
    def set_weights(self, weights: Dict[str, float]) -> None:
        """Assign target weights."""

    @abc.abstractmethod
    async def rebalance(self) -> None:
        """Trigger portfolio rebalancing."""

    @abc.abstractmethod
    def positions(self) -> Dict[str, float]:
        """Return current portfolio positions."""
