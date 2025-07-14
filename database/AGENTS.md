# Folder Overview

Database utilities built on psycopg2 for Postgres.
- `__init__.py` provides a lightweight wrapper around tables and queries.

- `schema.sql` defines all tables and is executed by `init_db`.
- `db_ping` verifies the Postgres connection at startup.
- Ticker universes are stored in dedicated tables for the S&P 400, S&P 500,
  S&P 600 and Russell 2000. The `ticker_returns` table includes an `index_name`
  column linking each ticker back to its source index.
The helpers are used by scrapers to store raw data and by strategies to fetch
historic metrics. Startup calls `init_db()` here to create tables. When
Postgres is unavailable the code falls back to an in-memory DuckDB database so
all components keep functioning.
