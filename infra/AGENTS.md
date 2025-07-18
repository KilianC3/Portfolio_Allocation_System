# Folder Overview

Supporting infrastructure used across the system.
- `smart_scraper.py` – resilient HTTP client used by all scrapers.
- `rate_limiter.py` – simple asyncio rate limiter.
- `data_store.py` – DuckDB helper for local caching.
- `charts/` and `grafana/` – static assets for observability dashboards.

These tools are imported by `scrapers/` and monitored via `observability/`.
The July 2025 release introduced a threaded scraper using `requests` to better
handle network proxies.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
