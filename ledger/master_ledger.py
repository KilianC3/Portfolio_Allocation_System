"""Master position ledger using Redis Streams."""

from __future__ import annotations

import os

import redis.asyncio as aioredis

from logger import get_logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_log = get_logger("ledger")


class MasterLedger:
    def __init__(self) -> None:
        self.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    async def reserve(self, pf_id: str, symbol: str, qty: float) -> str:
        """Reserve quantity before sending order."""
        key = f"ledger:{pf_id}:{symbol}"
        await self.redis.xadd(key, {"qty": qty, "status": "reserved"})
        return key

    async def commit(self, key: str, qty: float) -> None:
        """Commit a filled quantity."""
        await self.redis.xadd(key, {"qty": qty, "status": "filled"})

    async def current_position(self, pf_id: str, symbol: str) -> float:
        """Return filled position size."""
        key = f"ledger:{pf_id}:{symbol}"
        entries = await self.redis.xrange(key)
        pos = 0.0
        for _id, data in entries:
            if data.get("status") == "filled":
                pos += float(data.get("qty", 0))
        return pos

    async def free_float(self, pf_id: str, symbol: str) -> float:
        """Return filled minus reserved quantity."""
        key = f"ledger:{pf_id}:{symbol}"
        entries = await self.redis.xrange(key)
        filled = 0.0
        reserved = 0.0
        for _id, data in entries:
            qty = float(data.get("qty", 0))
            if data.get("status") == "filled":
                filled += qty
            elif data.get("status") == "reserved":
                reserved += qty
        return filled - reserved
