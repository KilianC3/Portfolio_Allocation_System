"""Configuration loaded from environment variables with validation."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
import os
from typing import Any, Dict


def _parse_simple_yaml(path: str) -> Dict[str, Any]:
    """Parse a minimal YAML mapping of `key: value` pairs."""
    data: Dict[str, Any] = {}
    with open(path) as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if val.lower() in {"true", "false"}:
                data[key] = val.lower() == "true"
            else:
                try:
                    data[key] = int(val)
                except ValueError:
                    try:
                        data[key] = float(val)
                    except ValueError:
                        data[key] = val
    return data


def _load_config_yaml(path: str = "config.yaml") -> None:
    """Populate environment variables from a YAML file if present."""
    if os.path.exists(path):
        for key, val in _parse_simple_yaml(path).items():
            os.environ.setdefault(key, str(val))


_load_config_yaml()


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables.

    ``config.yaml`` is parsed at import time and populates ``os.environ`` so
    these settings can be loaded without a separate ``.env`` file.
    """

    ALPACA_API_KEY: str | None = None
    ALPACA_API_SECRET: str | None = None
    ALPACA_BASE_URL: str = "https://paper-api.alpaca.markets"

    QUIVER_RATE_SEC: float = 1.1

    PG_URI: str = "postgresql://postgres:postgres@localhost:5432/quant_fund"

    MIN_ALLOC: float = Field(0.02, alias="MIN_ALLOCATION")
    MAX_ALLOC: float = Field(0.40, alias="MAX_ALLOCATION")

    REDDIT_CLIENT_ID: str | None = None
    REDDIT_CLIENT_SECRET: str | None = None
    REDDIT_USER_AGENT: str = "WSB-Strategy/1.0"

    API_TOKEN: str | None = None

    CACHE_TTL: int = Field(900, alias="CACHE_TTL")

    AUTO_START_SCHED: bool = False

    model_config = {"case_sensitive": False}


# Pass defaults explicitly so mypy recognises optional fields
settings = Settings(MIN_ALLOCATION=0.02, MAX_ALLOCATION=0.40, CACHE_TTL=900)

ALPACA_API_KEY = settings.ALPACA_API_KEY
ALPACA_API_SECRET = settings.ALPACA_API_SECRET
ALPACA_BASE_URL = settings.ALPACA_BASE_URL

QUIVER_RATE_SEC = settings.QUIVER_RATE_SEC

PG_URI = settings.PG_URI

MIN_ALLOC = settings.MIN_ALLOC
MAX_ALLOC = settings.MAX_ALLOC

REDDIT_CLIENT_ID = settings.REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET = settings.REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT = settings.REDDIT_USER_AGENT

API_TOKEN = settings.API_TOKEN
CACHE_TTL = settings.CACHE_TTL

CRON = {
    "monthly": {"day": "1", "hour": 3, "minute": 0},
    "weekly": {"day_of_week": "mon", "hour": 3, "minute": 0},
}

AUTO_START_SCHED = settings.AUTO_START_SCHED
