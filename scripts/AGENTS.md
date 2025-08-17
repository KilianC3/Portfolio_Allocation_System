# Folder Overview

Assorted command-line tools.
- `bootstrap.py` now delegates to `service.start.main`; it simply runs the
  system checklist and then launches the full startup sequence.
- `bootstrap.sh` assumes the repo is already downloaded, installs requirements and registers a systemd service. The MariaDB user and database are created automatically. Run scrapers manually if data backfilling is required.
- `setup_redis.sh` installs Redis, configures the bind address and enables the systemd service.
- `health_check.py` reports system status including portfolio and metric counts.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
