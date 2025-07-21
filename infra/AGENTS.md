# Folder Overview

Supporting infrastructure used across the system.
- `smart_scraper.py` – resilient HTTP client used by all scrapers.
- `rate_limiter.py` – simple asyncio rate limiter.
- `data_store.py` – DuckDB helper for local caching.
- `charts/` and `grafana/` – static assets for observability dashboards.

These tools are imported by `scrapers/` and monitored via `observability/`.
The July 2025 release introduced a threaded scraper using `requests` to better
handle network proxies.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
