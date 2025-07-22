# Repository Overview

This project implements a complete portfolio allocation system with data scrapers,
strategy modules and a FastAPI service for trading. Data is stored in Postgres.
Key folders:

- `scrapers/` – download alternative data and index constituents
- `analytics/` – compute fundamental and momentum metrics
- `strategies/` – build portfolios from database tables
- `risk/` – exposure limits and circuit breakers
- `service/` – API endpoints, scheduler and startup helpers
- `database/` – connection helpers and schema
- `docs/` – MkDocs documentation and agent guides

See `docs/AGENTS_ROOT.md` for detailed commit conventions.

## Commit Checklist

Before approving any commit, exhaustively inspect the codebase end‑to‑end. For
every file changed, added or renamed you must:
1. Summarise its purpose and any key classes or functions.
2. Trace upstream callers that rely on it and downstream modules it invokes.
3. List every folder or module that will need corresponding updates
   (tests, configs, docs, CI, API stubs, etc.).
4. Flag unreachable, duplicated or superseded files and recommend deletion.
5. Provide a total count and explicit paths of all impacted modules or folders.
   If any dependency edge is ambiguous, pause and ask for clarification rather
   than guessing.

