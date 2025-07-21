# Folder Overview

All data collection scripts.
- `universe.py` pulls ticker lists for the S&P 400, S&P 500 and Russell 2000. The Russell list is parsed from Wikipedia using the same helper as the other indices.
- `full_fundamentals.py` computes fundamental and price-based scores across the entire universe.
- `wiki.py` and others in this folder fetch alternative data from QuiverQuant and public APIs.

Scrapers call `init_db()` to ensure tables exist and the `universe` helper stores index constituents to Postgres and CSV.

The startup script runs each scraper sequentially and logs a checklist so you can verify every dataset was downloaded successfully.

Scrapers store their results via `database/` helpers and are triggered on
startup by the scheduler. Each scraper hits the URLs documented in the README,
including QuiverQuant pages and the Wikimedia API. Playwright is used for
Google Trends, lobbying and Finviz. All scrapers obtain a logger via
`get_scraper_logger(__name__)` so log output is consistent across modules.
Network errors are handled by a simple retry helper. The `DynamicRateLimiter`
ensures polite crawling so external services are not overwhelmed.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
