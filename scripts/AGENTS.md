# Folder Overview

Assorted command-line tools.
- `wsb_strategy.py` runs a WallStreetBets sentiment analysis for experimentation. The optional transformers dependency is handled gracefully so tests run without GPU support.
- `bootstrap.py` initialises the database and runs all scrapers once.
- `bootstrap.sh` installs requirements, seeds the data and registers a systemd service. The Postgres user and database must already exist.
- `health_check.py` reports system status including portfolio and metric counts.
