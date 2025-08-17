# Folder Overview

- `api.py` defines FastAPI endpoints and portfolio operations. Startup only logs
  readiness; all heavy initialisation happens elsewhere.
- `start.py` performs the full system checklist, initialises the database,
  loads portfolios, runs all scrapers and only then launches uvicorn.
- `scheduler.py` schedules recurring jobs using APScheduler.
- `logger.py` wraps the structlog helpers for consistent logging.
- `config.py` and `config.yaml` hold environment configuration.

Blocking database updates in endpoints are wrapped with
`asyncio.to_thread` so FastAPI's event loop remains responsive. The
connection pool size is configurable via `DB_POOL_SIZE` and only warnings
and errors are stored in `system_logs`.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
