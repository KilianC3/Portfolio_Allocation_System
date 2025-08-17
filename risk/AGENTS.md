# Folder Overview

Risk management models and limits.
- `circuit.py` – circuit breaker checks for portfolio losses.
- `position_risk.py` and `var.py` – value-at-risk calculations.

Strategies query these modules before executing trades.
The circuit breaker logs breach events to MariaDB so tests can verify
triggered stops even without a live database connection.

FRED time series are fetched concurrently via `httpx.AsyncClient` to
avoid blocking delays.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
