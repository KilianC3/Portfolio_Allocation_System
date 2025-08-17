# Folder Overview

MkDocs site containing extended documentation.
- `index.md` – entry point for the docs.
- `data_format.md` – describes scraped dataset schema.

Documentation covers the new `universe` table and extended metrics fields.
The README provides setup instructions while these pages dive into
implementation details. Recent documentation updates list every data source URL,
explain how scrapers run automatically at startup, describe the
`index_name` field in `ticker_scores` and document metrics like
`weekly_vol`, `weekly_sortino`, `atr_14d` and `rsi_14d`.

New notes cover the `DB_POOL_SIZE` setting and schema indexes on
`metrics(portfolio_id)` and `ticker_scores(index_name)`.

- **Reminder:** triple-check modifications and run tests to prevent regressions.

Before approving this commit, exhaustively inspect the codebase end-to-end. For every file changed, added, or renamed, (1) summarise its purpose and key classes/functions, (2) trace upstream callers that rely on it and downstream modules it invokes, and (3) list every folder or module that will therefore need corresponding updates (tests, configs, docs, CI scripts, API stubs, etc.). While traversing, flag any file that has become unreachable, duplicated, or superseded and recommend explicit deletion; the final state must contain no obsolete artefacts. Provide a total count and explicit paths of all impacted modules/folders. If at any point a dependency graph edge is ambiguous, a migration step is unclear, or removal of a legacy file is debatable, pause and ask for clarification rather than guessing.
