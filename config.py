"""Configuration loaded from environment variables with validation."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from ``.env`` or environment."""

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

    AUTO_START_SCHED: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()  # will raise ValidationError on bad env values

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

CRON = {
    "monthly": {"day": "1", "hour": 3, "minute": 0},
    "weekly": {"day_of_week": "mon", "hour": 3, "minute": 0},
}

AUTO_START_SCHED = settings.AUTO_START_SCHED
