# Folder Overview

The `backtest` package holds historical simulation tools.
- `engine.py` – simple driver for running strategies on past data.

It relies on scrapers in `scrapers/` to provide price and event data and uses
`analytics/` modules to evaluate performance. The July 2025 update added
support for running the full strategy suite with mocked market data so tests
can verify portfolio construction without downloading large datasets.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
