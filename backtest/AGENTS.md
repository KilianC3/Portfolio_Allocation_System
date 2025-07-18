# Folder Overview

The `backtest` package holds historical simulation tools.
- `engine.py` – simple driver for running strategies on past data.

It relies on scrapers in `scrapers/` to provide price and event data and uses
`analytics/` modules to evaluate performance. The July 2025 update added
support for running the full strategy suite with mocked market data so tests
can verify portfolio construction without downloading large datasets.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
