# Portfolio Allocation System (PAS)

The Portfolio Allocation System is an end‑to‑end platform for constructing and
managing multi‑strategy equity portfolios.  It combines data collection,
analytics, execution and reporting in a single deployable service.

## Features

- **Flexible allocation engine** – supports max‑Sharpe (default), risk parity,
  minimum variance, strategic (SAA), tactical (TAA) and dynamic schemes.  Each
  method is evaluated continuously so historical performance can be compared.
- **Fama–French analytics** – market, size and value factors are used to
  estimate expected returns and portfolio betas.
- **Comprehensive ledger** – Redis backed ledger tracks reservations,
  executions and cancellations and exposes current positions and free float.
- **Real‑time metrics** – metrics and system log events are broadcast over a
  WebSocket hub; the updater task aggregates daily returns and exposures for
  dashboards.
- **Rich front end** – Chart.js visualisations render risk metrics, returns and
  sector weights with CSV/PNG export helpers for reporting.

## Architecture

The repository follows a modular layout:

| Folder | Purpose |
| ------ | ------- |
| `analytics/` | factor models, allocation engine and performance tracking |
| `core/` | portfolio model with weight normalisation and PnL helpers |
| `ledger/` | Redis based trade ledger and position summaries |
| `service/` | FastAPI application, configuration and caching utilities |
| `tasks/` | background updater loop that refreshes metrics and broadcasts events |
| `frontend/` | React components and utilities for charts and sockets |
| `docs/` | additional documentation including WebSocket protocol details |

MariaDB stores persistent data while Redis caches hot metrics and maintains the
trade ledger.  All services can run locally or inside Docker containers.

## Getting Started

### Requirements

- Python 3.10+
- MariaDB 10+
- Redis 6+
- Alpaca API key for order routing (paper or live)

### Installation

1. Clone the repository.
2. Populate `service/config.yaml` with database and API credentials. Cron
   schedules for background jobs are now defined in `service/config.py` and do
   not require entries in the YAML file.
3. Install dependencies:

   ```bash
   pip install -r deploy/requirements.txt
   ```

4. Initialise the database schema:

   ```bash
   python -m database.init_db
   ```

5. Start the API and background updater:

   ```bash
   python -m service.start &
   python scripts/run_updater.py &
   ```

Interactive docs are available at `http://localhost:8000/docs` and a simple
dashboard at `http://localhost:8000/dashboard`.

## Testing

Run the unit test suite before submitting changes:

```bash
pytest -q
```

## Contributing

Pull requests are welcome.  Please keep commits focused, format Python with
`black`, update documentation for behavioural changes and ensure `pytest -q`
passes.

## License

This project is released under the MIT license.

