"""Configuration loaded from environment variables with validation."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
import os
from typing import Any, Dict
from pathlib import Path
from apscheduler.triggers.cron import CronTrigger

from service.logger import get_logger


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


def _load_config_yaml(path: str | None = None) -> None:
    """Populate environment variables from a YAML file if present."""
    cfg = Path(path) if path else Path(__file__).with_name("config.yaml")
    if cfg.exists():
        for key, val in _parse_simple_yaml(str(cfg)).items():
            os.environ.setdefault(key, str(val))


_load_config_yaml()

_log = get_logger("config")


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables.

    ``config.yaml`` is parsed at import time and populates ``os.environ`` so
    these settings can be loaded without a separate ``.env`` file.
    """

    ALPACA_PAPER_KEY: str | None = None
    ALPACA_PAPER_SECRET: str | None = None
    ALPACA_PAPER_URL: str = "https://paper-api.alpaca.markets"
    ALPACA_LIVE_KEY: str | None = None
    ALPACA_LIVE_SECRET: str | None = None
    ALPACA_LIVE_URL: str = "https://api.alpaca.markets"
    ALLOW_LIVE: bool = False

    QUIVER_RATE_SEC: float = 1.1

    DB_URI: str = "mysql+pymysql://maria:maria@192.168.0.59:3306/quant_fund"

    FRED_API_KEY: str | None = None

    MIN_ALLOC: float = Field(0.02, alias="MIN_ALLOCATION")
    MAX_ALLOC: float = Field(0.40, alias="MAX_ALLOCATION")

    API_TOKEN: str | None = None

    API_HOST: str = "192.168.0.59"
    API_PORT: int = 8001

    REDIS_URL: str = "redis://192.168.0.59:6379/0"

    CACHE_TTL: int = Field(900, alias="CACHE_TTL")
    CACHE_BACKEND: str = Field("memory", alias="CACHE_BACKEND")

    LEDGER_STREAM_MAXLEN: int = Field(1000, alias="LEDGER_STREAM_MAXLEN")

    ALLOC_METHOD: str = Field("max_sharpe", alias="ALLOC_METHOD")

    AUTO_START_SCHED: bool = False

    model_config = {"case_sensitive": False}


# Pass defaults explicitly so mypy recognises optional fields
settings = Settings(
    MIN_ALLOCATION=0.02,
    MAX_ALLOCATION=0.40,
    CACHE_TTL=900,
    CACHE_BACKEND="memory",
    LEDGER_STREAM_MAXLEN=1000,
    ALLOC_METHOD="max_sharpe",
)

ALLOW_LIVE = settings.ALLOW_LIVE

ALPACA_API_KEY = settings.ALPACA_LIVE_KEY if ALLOW_LIVE else settings.ALPACA_PAPER_KEY
ALPACA_API_SECRET = (
    settings.ALPACA_LIVE_SECRET if ALLOW_LIVE else settings.ALPACA_PAPER_SECRET
)
ALPACA_BASE_URL = settings.ALPACA_LIVE_URL if ALLOW_LIVE else settings.ALPACA_PAPER_URL

QUIVER_RATE_SEC = settings.QUIVER_RATE_SEC

DB_URI = settings.DB_URI

MIN_ALLOC = settings.MIN_ALLOC
MAX_ALLOC = settings.MAX_ALLOC


FRED_API_KEY = settings.FRED_API_KEY

API_TOKEN = settings.API_TOKEN
CACHE_TTL = settings.CACHE_TTL
CACHE_BACKEND = settings.CACHE_BACKEND

LEDGER_STREAM_MAXLEN = settings.LEDGER_STREAM_MAXLEN

ALLOC_METHOD = settings.ALLOC_METHOD

API_HOST = settings.API_HOST
API_PORT = settings.API_PORT

CRON = {
    "monthly": {"day": "1", "hour": 3, "minute": 0},
    "weekly": {"day_of_week": "mon", "hour": 3, "minute": 0},
}

AUTO_START_SCHED = settings.AUTO_START_SCHED

REDIS_URL = settings.REDIS_URL
if not REDIS_URL:
    token = settings.API_TOKEN or "changeme"
    REDIS_URL = f"redis://:{token}@192.168.0.59:6379/0"

# Default cron-style schedules for periodic jobs
DEFAULT_SCHEDULES = {
    "metrics": "5 0 * * *",
    "ticker_scores": "0 3 1 * *",
    "wsb_mentions": "0 3 1 * *",
    "account": "0 0 * * *",
    "risk_stats": "30 0 * * *",
    "risk_rules": "*/5 * * * *",
    "politician_trades": "0 2 * * *",
    "lobbying": "30 2 * * 1",
    "wiki_trending": "0 3 * * *",
    "wiki_views": "30 3 * * *",
    "dc_insider": "0 4 * * 1",
    "gov_contracts": "0 5 * * *",
    "app_reviews": "0 6 * * *",
    "google_trends": "0 7 * * *",
    "insider_buying": "0 8 * * *",
    "vol_mom": "0 9 * * 1",
    "lev_sector": "30 9 * * 1",
    "sector_mom": "0 10 * * 1",
    "smallcap_mom": "30 10 * * 1",
    "upgrade_mom": "0 11 * * 1",
}

# Allow overrides via environment variables prefixed with SCHED_
SCHEDULES = DEFAULT_SCHEDULES | {
    k[6:].lower(): v for k, v in os.environ.items() if k.startswith("SCHED_")
}

for name, expr in SCHEDULES.items():
    try:
        CronTrigger.from_crontab(expr)
    except ValueError as exc:  # pragma: no cover - misconfig
        _log.error("invalid cron schedule", job=name, expr=expr)
        raise RuntimeError(f"invalid cron schedule for {name}: {expr}") from exc
