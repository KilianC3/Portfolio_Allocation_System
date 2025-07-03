"""Simple circuit breaker."""

from __future__ import annotations

import datetime as dt
from typing import Optional


class CircuitBreaker:
    """Pauses trading when triggered."""

    def __init__(self, cooldown_minutes: int = 30):
        self.cooldown_minutes = cooldown_minutes
        self._tripped: Optional[dt.datetime] = None

    @property
    def tripped(self) -> bool:
        if not self._tripped:
            return False
        return dt.datetime.utcnow() < self._tripped + dt.timedelta(minutes=self.cooldown_minutes)

    def trip(self) -> None:
        self._tripped = dt.datetime.utcnow()

    def reset(self) -> None:
        self._tripped = None

__all__ = ["CircuitBreaker"]
