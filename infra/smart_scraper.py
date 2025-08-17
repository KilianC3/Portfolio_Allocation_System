"""Resilient async HTTP scraper with caching and rate limits."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import random

import httpx

from service.config import CACHE_TTL
from service.logger import get_logger

from infra.rate_limiter import DynamicRateLimiter
from database import cache


USER_AGENTS = ["Mozilla/5.0", "Chrome/122.0", "Safari/537.36"]
"""List of user agents rotated on each request."""

RATE = DynamicRateLimiter(12, 60)
"""Scrape at most 12 pages per minute."""

TTL = CACHE_TTL
"""Cache expiry for fetched pages (seconds)."""


log = get_logger(__name__)


async def get(url: str, retries: int = 3) -> str:
    """Fetch ``url`` asynchronously with caching and basic retries.

    Uses ``httpx.AsyncClient`` and respects the dynamic rate limiter.
    Adds detailed logging for cache hits and retry attempts.
    """

    key = hashlib.md5(url.encode()).hexdigest()
    doc = cache.find_one({"cache_key": key})
    if doc:
        expire = doc.get("expire")
        if expire is not None:
            # normalise to UTC if timezone info missing
            if expire.tzinfo is None:
                expire = expire.replace(tzinfo=dt.timezone.utc)
        if expire is not None and expire > dt.datetime.now(dt.timezone.utc):
            log.debug("cache hit %s", url)
            return doc["payload"]
        log.debug("cache expired %s", url)

    backoff = 1.0
    async with RATE:
        error: Exception | None = None
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(retries):
                try:
                    log.info("fetch attempt %s/%s %s", attempt + 1, retries, url)
                    resp = await client.get(
                        url, headers={"User-Agent": random.choice(USER_AGENTS)}
                    )
                    resp.raise_for_status()
                    text = resp.text
                    log.debug("fetched %d chars from %s", len(text), url)
                    cache.replace_one(
                        {"cache_key": key},
                        {
                            "cache_key": key,
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
                    log.warning("fetch attempt %s failed: %s", attempt + 1, exc)
                    await asyncio.sleep(backoff)
                    backoff *= 2
        raise RuntimeError(f"Failed {url}: {error}")
