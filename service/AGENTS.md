# Folder Overview

Service layer exposing the REST API and scheduler.
- `api.py` defines FastAPI endpoints and portfolio operations.
- `start.py` validates startup and runs all scrapers once.
- `scheduler.py` schedules recurring jobs using APScheduler.
- `logger.py` wraps the structlog helpers for consistent logging.
- `config.py` and `config.yaml` hold environment configuration.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
