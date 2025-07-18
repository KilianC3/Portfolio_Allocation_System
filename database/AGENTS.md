# Folder Overview

Database utilities built on psycopg2 for Postgres.
- `__init__.py` provides a lightweight wrapper around tables and queries.

- `schema.sql` defines all tables and is executed by `init_db`.
- `db_ping` verifies the Postgres connection at startup.
- Ticker universes are stored in dedicated tables for the S&P 400, S&P 500,
  and Russell 2000. The `ticker_scores` table stores composite metrics for
  each ticker along with its `index_name`.
The helpers are used by scrapers to store raw data and by strategies to fetch
historic metrics. Startup calls `init_db()` here to create tables. When
Postgres is unavailable the code falls back to an in-memory DuckDB database so
all components keep functioning.

- **Reminder:** triple-check modifications and run tests to prevent regressions.
