# Folder Overview

All data collection scripts.
- `universe.py` pulls ticker lists for the S&P 400, S&P 500 and Russell 2000.
- `finviz_fundamentals.py` scrapes key ratios like Piotroski F‑Score and Altman Z‑Score.
- `wiki.py` and others in this folder fetch alternative data from QuiverQuant and public APIs.

Scrapers call `init_db()` to ensure tables exist and the `universe` helper stores index constituents to Postgres and CSV.

The startup script runs each scraper sequentially and logs a checklist so you can verify every dataset was downloaded successfully.

Scrapers store their results via `database/` helpers and are triggered on
startup by the scheduler. Each scraper hits the URLs documented in the README,
including QuiverQuant pages and the Wikimedia API. A threaded scraper with
`requests` retries downloads when network errors occur.
