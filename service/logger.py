from observability.logging import get_logger, add_db_handler


def register_db_handler(coll) -> None:
    """Add a handler that stores all logs in ``coll``."""
    add_db_handler(coll)


__all__ = ["get_logger", "register_db_handler"]
