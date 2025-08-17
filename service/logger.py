import logging
from observability.logging import get_logger, add_db_handler


def get_scraper_logger(name: str):
    """Return a logger with a ``scrapers.`` prefix.

    Using this helper ensures all scraper modules share a consistent
    namespace even when executed as standalone scripts.
    """
    module = name.rsplit(".", 1)[-1]
    return get_logger(f"scrapers.{module}")


def register_db_handler(coll) -> None:
    """Add a handler that stores warnings and errors in ``coll``."""
    add_db_handler(coll, level=logging.WARNING)


__all__ = ["get_logger", "get_scraper_logger", "register_db_handler"]
