import logging
import os
import uuid
import structlog
from logging.handlers import RotatingFileHandler
from typing import Dict, Tuple
import datetime as dt
import time

try:  # systemd journal available in deployment but optional in tests
    from systemd.journal import JournalHandler  # type: ignore
except Exception:  # pragma: no cover - platform dependent
    JournalHandler = None

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class _DedupFilter(logging.Filter):
    """Suppress identical messages within a short window."""

    def __init__(self, window: int = 60) -> None:
        super().__init__()
        self.window = window
        self._last: Dict[Tuple[int, str], float] = {}

    def filter(
        self, record: logging.LogRecord
    ) -> bool:  # pragma: no cover - timing varies
        key = (record.levelno, record.getMessage())
        now = time.time()
        prev = self._last.get(key, 0)
        self._last[key] = now
        return now - prev > self.window


level = os.getenv("LOG_LEVEL", "INFO").upper()
handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "app.log"), maxBytes=1_000_000, backupCount=3
)
handler.addFilter(_DedupFilter())
_handlers = [handler]
if JournalHandler is not None:
    _handlers.append(JournalHandler())
logging.basicConfig(
    level=getattr(logging, level, logging.INFO),
    format="%(message)s",
    handlers=_handlers,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
)


def get_logger(name: str):
    return structlog.get_logger(name).bind(trace_id=str(uuid.uuid4()))


class DBHandler(logging.Handler):
    """Simple log handler that writes records to a DB collection."""

    def __init__(self, coll) -> None:
        super().__init__()
        self.coll = coll

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - db optional
        try:
            self.coll.insert_one(
                {
                    "timestamp": dt.datetime.fromtimestamp(
                        record.created, dt.timezone.utc
                    ),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            pass


def add_db_handler(coll, level: int = logging.WARNING) -> None:
    """Attach a database log handler to the root logger."""
    handler = DBHandler(coll)
    handler.setLevel(level)
    logging.getLogger().addHandler(handler)


def clear_log_files() -> None:
    """Remove all rotated log files under ``LOG_DIR``."""
    for name in os.listdir(LOG_DIR):
        if name.startswith("app.log"):
            try:
                os.remove(os.path.join(LOG_DIR, name))
            except OSError:
                pass
