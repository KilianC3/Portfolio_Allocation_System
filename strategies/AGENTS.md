# Folder Overview

Portfolio construction logic for each trading strategy.
Files here call out to `scrapers/` for data and rely on `analytics/` and
`risk/` modules to compute weights and limits. Each strategy exposes a
`build()` coroutine that updates a portfolio instance.
Strategies now cover the Congressional-Trading Aggregate, DC insider scores,
government contracts, app reviews, Google Trends and politician sleeves for
Nancy Pelosi, Dan Meuser and Shelley Moore Capito. They are executed on a
schedule and validated by unit tests.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
