"""Resilient async HTTP scraper with caching and rate limits."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import random

import requests

from config import CACHE_TTL

from infra.rate_limiter import DynamicRateLimiter
from database import cache


USER_AGENTS = ["Mozilla/5.0", "Chrome/122.0", "Safari/537.36"]
"""List of user agents rotated on each request."""

RATE = DynamicRateLimiter(12, 60)
"""Scrape at most 12 pages per minute."""

TTL = CACHE_TTL
"""Cache expiry for fetched pages (seconds)."""


async def get(url: str, retries: int = 3) -> str:
    """Fetch ``url`` asynchronously with caching and basic retries.

    Uses ``requests`` inside a thread so network calls work behind proxies.
    """

    key = hashlib.md5(url.encode()).hexdigest()
    doc = cache.find_one({"key": key})
    if doc:
        expire = doc.get("expire")
        if expire is not None and expire > dt.datetime.now(dt.timezone.utc):
            return doc["payload"]

    backoff = 1.0
    async with RATE:
        error: Exception | None = None
        for attempt in range(retries):
            try:

                def _fetch() -> str:
                    r = requests.get(
                        url,
                        headers={"User-Agent": random.choice(USER_AGENTS)},
                        timeout=15,
                    )
                    r.raise_for_status()
                    return r.text

                text = await asyncio.to_thread(_fetch)
                cache.replace_one(
                    {"key": key},
                    {
                        "key": key,
                        "payload": text,
                        "expire": dt.datetime.now(dt.timezone.utc)
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
