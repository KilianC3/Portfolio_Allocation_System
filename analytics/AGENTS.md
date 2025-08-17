# Folder Overview

This package contains analytics utilities used by the allocation engine.
Key modules:
-- `covariance.py` – covariance estimation helpers.
-- `robust.py` and `tracking.py` – robust statistics and performance tracking.
-- `account.py` – scrape account metrics.
Portfolio metrics compute rolling 7-day, 30-day and 1-year returns and append results to CSV files in cache/metrics/.
Allocation logs capture the expected return, covariance matrix and final weights so the UI can show complete diagnostics.
The helper `lambda_from_half_life()` converts a chosen half-life into an exponential decay factor used by the covariance calculations.

These modules operate on portfolio objects from `core/` and store results
through the `database/` helpers. Strategies in `strategies/` rely on these
functions to build portfolios. Recent commits added a max_sharpe allocator (default) and alternatives such as risk parity, minimum variance, strategic, tactical and dynamic mixes. Tests under
`tests/` validate the analytics helpers with mocked data.

Ticker score and return aggregation routines batch inserts with
`insert_many` to minimise per-row latency when writing to MariaDB.

## Allocation Tips
- Keep weight computation simple to avoid estimation error when signals overlap.
- The max_sharpe allocator assumes recent weekly returns are representative; verify your data quality before relying on it.
- When signal quality is uncertain, favour volatility scaling or equal-weight fallbacks for stability.
- Clip extreme weekly returns before estimating covariance and revert to the
  previous allocation if the computed volatility is clearly abnormal.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
