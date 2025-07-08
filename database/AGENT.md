# Folder Overview

Database utilities built on psycopg2 for Postgres.
- `__init__.py` provides a lightweight wrapper around tables and queries.

The helpers are used by scrapers to store raw data and by strategies to fetch
historic metrics. Startup calls `init_db()` here to create tables.
