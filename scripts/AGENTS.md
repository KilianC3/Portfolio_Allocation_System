# Folder Overview

Assorted command-line tools.
- `wsb_cli.py` runs a WallStreetBets sentiment analysis for experimentation. The optional transformers dependency is handled gracefully so tests run without GPU support.
- `bootstrap.py` initialises the database, verifies connectivity via a
  system checklist and then runs all scrapers once.
 - `bootstrap.sh` assumes the repo is already downloaded, installs requirements, runs all scrapers once and registers a systemd service. The MariaDB user and database are created automatically.
- `health_check.py` reports system status including portfolio and metric counts.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
