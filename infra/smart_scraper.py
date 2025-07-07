"""Resilient async HTTP scraper with caching and rate limits."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import random
from typing import Optional

import aiohttp

from infra.rate_limiter import DynamicRateLimiter
from database import cache


USER_AGENTS = ["Mozilla/5.0", "Chrome/122.0", "Safari/537.36"]
"""List of user agents rotated on each request."""

RATE = DynamicRateLimiter(12, 60)
"""Scrape at most 12 pages per minute."""

TTL = 900
"""Cache expiry for fetched pages (seconds)."""

_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    """Return a shared :class:`aiohttp.ClientSession`."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )
    return _session


async def close_session() -> None:
    """Close the shared HTTP session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None


async def get(url: str, retries: int = 3) -> str:
    """Fetch ``url`` asynchronously with caching and basic retries."""

    key = hashlib.md5(url.encode()).hexdigest()
    doc = cache.find_one({"key": key})
    if doc and doc["expire"] > dt.datetime.utcnow():
        return doc["payload"]

    backoff = 1.0
    async with RATE:
        session = await _get_session()
        for attempt in range(retries):
            try:
                async with session.get(
                    url,
                    headers={"User-Agent": random.choice(USER_AGENTS)},
                ) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        cache.replace_one(
                            {"key": key},
                            {
                                "key": key,
                                "payload": text,
                                "expire": dt.datetime.utcnow()
                                + dt.timedelta(seconds=TTL),
                            },
                            upsert=True,
                        )
                        RATE.reset()
                        return text
                    else:
                        RATE.backoff()
            except Exception as exc:
                err = exc
                RATE.backoff()
            await asyncio.sleep(backoff)
            backoff *= 2
        raise RuntimeError(f"Failed {url}: {err}")

