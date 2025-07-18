# Folder Overview

Ledger utilities for transaction records.
- `master_ledger.py` manages a full history of trades for auditing.

Trade data is ingested from the `execution/` layer and summarised by
`analytics/` tools. Recent updates added DuckDB snapshots so ledger histories
survive restarts when Postgres is unavailable.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
