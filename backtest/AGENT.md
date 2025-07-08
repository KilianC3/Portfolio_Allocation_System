# Folder Overview

The `backtest` package holds historical simulation tools.
- `engine.py` – simple driver for running strategies on past data.

It relies on scrapers in `scrapers/` to provide price and event data and uses
`analytics/` modules to evaluate performance.
