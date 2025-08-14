"""Simple in-memory caching utilities for service endpoints."""

from __future__ import annotations

import time
from threading import RLock
from typing import Any

from service.config import CACHE_TTL, CACHE_BACKEND

_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = RLock()


def get(key: str) -> Any | None:
    """Return cached value if present and not expired."""
    if CACHE_BACKEND != "memory":
        return None
    with _LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        expiry, value = item
        if expiry and expiry < time.monotonic():
            _CACHE.pop(key, None)
            return None
        return value


def set(key: str, value: Any, ttl: int | None = None) -> None:
    """Store ``value`` under ``key`` for ``ttl`` seconds."""
    if CACHE_BACKEND != "memory":
        return
    ttl = CACHE_TTL if ttl is None else ttl
    expiry = time.monotonic() + ttl if ttl else 0
    with _LOCK:
        _CACHE[key] = (expiry, value)


def invalidate_prefix(prefix: str) -> None:
    """Remove all cache entries starting with ``prefix``."""
    if CACHE_BACKEND != "memory":
        return
    with _LOCK:
        for k in list(_CACHE.keys()):
            if k.startswith(prefix):
                _CACHE.pop(k, None)


def clear() -> None:
    """Clear the entire cache (primarily for tests)."""
    with _LOCK:
        _CACHE.clear()


__all__ = ["get", "set", "invalidate_prefix", "clear"]
