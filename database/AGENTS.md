# Folder Overview

Database utilities built on PyMySQL for MariaDB.
- `__init__.py` provides a lightweight wrapper around tables and queries.

- `schema.sql` defines all tables and is executed by `init_db`.
- `db_ping` verifies the MariaDB connection at startup.
- Ticker universes are stored in dedicated tables for the S&P 400, S&P 500,
  and Russell 2000. The `ticker_scores` table stores composite metrics for
  each ticker along with its `index_name`.
The helpers are used by scrapers to store raw data and by strategies to fetch
historic metrics. Startup calls `init_db()` here to create tables. If MariaDB
is unavailable the collections simply become no-ops so tests can run without a
database.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
