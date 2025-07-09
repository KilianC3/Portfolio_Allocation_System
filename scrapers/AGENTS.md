# Folder Overview

All data collection scripts.
- `universe.py` pulls ticker lists.
- `wiki.py` and others in this folder fetch alternative data from QuiverQuant
  and public APIs.

Scrapers store their results via `database/` helpers and are triggered on
startup by the scheduler. Each scraper hits the URLs documented in the README,
including QuiverQuant pages and the Wikimedia API. A threaded scraper with
`requests` retries downloads when network errors occur.
