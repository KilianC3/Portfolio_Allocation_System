# Folder Overview

This package contains analytics utilities used by the allocation engine.
Key modules:
- `blacklitterman.py` – compute market implied returns and Black–Litterman posterior.
- `covariance.py` – covariance estimation helpers.
- `robust.py` and `tracking.py` – robust statistics and performance tracking.
- `account.py` and `collector.py` – scrape account metrics and collect statistics.

These modules operate on portfolio objects from `core/` and store results
through the `database/` helpers. Strategies in `strategies/` rely on these
functions to build portfolios. Recent commits added dynamic return models and
Black--Litterman views that feed into the allocation engine. Tests under
`tests/` validate the analytics helpers with mocked data.
