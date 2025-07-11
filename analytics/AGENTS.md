# Folder Overview

This package contains analytics utilities used by the allocation engine.
Key modules:
-- `covariance.py` – covariance estimation helpers.
-- `robust.py` and `tracking.py` – robust statistics and performance tracking.
-- `account.py` and `collector.py` – scrape account metrics and collect statistics.
Portfolio metrics compute rolling 7-day, 30-day and 1-year returns and append results to CSV files in cache/metrics/.
Allocation logs capture the expected return, covariance matrix and final weights so the UI can show complete diagnostics.
The helper `lambda_from_half_life()` converts a chosen half-life into an exponential decay factor used by the covariance calculations.

These modules operate on portfolio objects from `core/` and store results
through the `database/` helpers. Strategies in `strategies/` rely on these
functions to build portfolios. Recent commits introduced a tangency allocator that maximises the Sharpe ratio. Tests under
`tests/` validate the analytics helpers with mocked data.

## Allocation Tips
- Keep weight computation simple to avoid estimation error when signals overlap.
- The tangency allocator assumes recent weekly returns are representative; verify your data quality before relying on it.
- When signal quality is uncertain, favour volatility scaling or equal-weight fallbacks for stability.
- Clip extreme weekly returns before estimating covariance and revert to the
  previous allocation if the computed volatility is clearly abnormal.
