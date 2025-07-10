# Folder Overview

This package contains analytics utilities used by the allocation engine.
Key modules:
- `blacklitterman.py` – compute market implied returns and Black–Litterman posterior.
- `covariance.py` – covariance estimation helpers.
- `robust.py` and `tracking.py` – robust statistics and performance tracking.
- `account.py` and `collector.py` – scrape account metrics and collect statistics.
Portfolio metrics compute rolling 7-day, 30-day and 1-year returns and append results to CSV files in cache/metrics/.
Allocation logs capture each portfolio's volatility, momentum and beta values next to the final weights so the UI can show complete diagnostics.
The helper `lambda_from_half_life()` converts a chosen half-life into an exponential decay factor used by the covariance and Black–Litterman calculations.

These modules operate on portfolio objects from `core/` and store results
through the `database/` helpers. Strategies in `strategies/` rely on these
functions to build portfolios. Recent commits added dynamic return models and
Black--Litterman views that feed into the allocation engine. Tests under
`tests/` validate the analytics helpers with mocked data.

## Allocation Tips
- Keep weight computation simple to avoid estimation error when signals overlap.
- Black--Litterman plus risk parity works best with reliable views and low noise.
- When signal quality is uncertain, favour hierarchical risk parity with momentum and dynamic leverage for stability.
- Clip extreme weekly returns before estimating covariance and revert to the
  previous allocation if the computed volatility is clearly abnormal.
