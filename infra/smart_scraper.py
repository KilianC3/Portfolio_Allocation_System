"""Resilient async HTTP scraper with caching and rate limits."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import random

import aiohttp

from infra.rate_limiter import DynamicRateLimiter
from database import cache


USER_AGENTS = ["Mozilla/5.0", "Chrome/122.0", "Safari/537.36"]
"""List of user agents rotated on each request."""

RATE = DynamicRateLimiter(12, 60)
"""Scrape at most 12 pages per minute."""

TTL = 900
"""Cache expiry for fetched pages (seconds)."""


async def get(url: str, retries: int = 3) -> str:
    """Fetch ``url`` asynchronously with caching and basic retries."""

    key = hashlib.md5(url.encode()).hexdigest()
    doc = cache.find_one({"key": key})
    if doc and doc["expire"] > dt.datetime.utcnow():
        return doc["payload"]

    backoff = 1.0
    async with RATE:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            error: Exception | None = None
            for attempt in range(retries):
                try:
                    async with session.get(
                        url,
                        headers={"User-Agent": random.choice(USER_AGENTS)},
                    ) as resp:
                        resp.raise_for_status()
                        text = await resp.text()
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
                except Exception as exc:
                    RATE.backoff()
                    error = exc
                    await asyncio.sleep(backoff)
                    backoff *= 2
            raise RuntimeError(f"Failed {url}: {error}")
