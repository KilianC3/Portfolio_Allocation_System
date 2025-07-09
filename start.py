import uvicorn

from config import API_TOKEN, PG_URI, CACHE_TTL
from database import db_ping, init_db
from scrapers.universe import download_sp1500, download_russell2000


def validate_startup() -> None:
    """Ensure config and tables exist before starting the API."""
    if not PG_URI:
        raise RuntimeError("PG_URI not set")
    if not API_TOKEN:
        raise RuntimeError("API_TOKEN not set")
    if CACHE_TTL <= 0:
        raise RuntimeError("CACHE_TTL must be positive")
    if not db_ping():
        raise RuntimeError("Postgres connection failed")
    init_db()
    download_sp1500()
    download_russell2000()


if __name__ == "__main__":
    validate_startup()
    uvicorn.run("api:app", host="0.0.0.0", port=8001)
