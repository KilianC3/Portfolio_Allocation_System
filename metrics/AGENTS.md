# Folder Overview

Shared Prometheus metrics setup.
- `__init__.py` registers app metrics for monitoring scraping and trading.

Used by the API module and the scheduler to expose real-time statistics.
Recent commits expanded metrics to track scraper success counts and strategy
weights for regression tests.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
