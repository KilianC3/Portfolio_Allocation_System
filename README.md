# Portfolio Allocation System

This project implements a minimal portfolio management API and scraping suite built with Python. It provides tools to schedule trading strategies, collect alternative data and record trades in a MongoDB database.

## Prerequisites

- Python 3.12+
- MongoDB instance (local or remote)
- Optional: Alpaca brokerage account for trade execution

## Installation

1. **Clone the repository**
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   ```
2. **Create a virtual environment** *(recommended)*
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Environment variables control connections and limits. Create a `.env` file or export variables in your shell.

- `ALPACA_API_KEY` and `ALPACA_API_SECRET` – credentials for Alpaca Trade API.
- `ALPACA_BASE_URL` – API endpoint (default `https://paper-api.alpaca.markets`).
- `QUIVER_API_KEY` – API key for QuiverQuant data.
- `QUIVER_RATE_SEC` – seconds between scraper requests (default `1.1`).
- `MONGO_URI` – MongoDB connection URI (default `mongodb://localhost:27017`).
- `DB_NAME` – MongoDB database name (default `quant_fund`).
- `MIN_ALLOCATION` and `MAX_ALLOCATION` – portfolio weight bounds.

## Running the API

Start the FastAPI server with Uvicorn:
```bash
uvicorn api:app --reload
```
The API exposes endpoints to manage portfolios, trigger scrapers and check scheduled jobs. See `api.py` for full route definitions.

## Background Scheduler

`StrategyScheduler` in `scheduler.py` runs trading strategies on a cron schedule using APScheduler. Strategies are Python classes under `strategies/` with a `build` coroutine that sets portfolio weights and executes trades.

Example usage:
```python
from scheduler import StrategyScheduler
sched = StrategyScheduler()
sched.add('lobby', 'Lobbying', 'strategies.lobbying_growth', 'LobbyingGrowthStrategy', 'monthly')
sched.start()
```
The scheduler also runs a weekly rebalancing job that uses metrics stored in MongoDB to compute new allocations via `allocation_engine.compute_weights`.

## Scrapers

Modules in `scrapers/` fetch datasets from QuiverQuant. Each function returns a list of records and stores them in the database:

- `politician.py` – congressional trading disclosures
- `lobbying.py` – corporate lobbying spending
- `wiki.py` – Wikipedia page view statistics
- `dc_insider.py` – insider sentiment scores
- `gov_contracts.py` – government contract awards

Scrapers share a simple caching mechanism via `infra.smart_scraper.get` and respect rate limits using `infra.rate_limiter.AsyncRateLimiter`.

## Portfolio Management

`portfolio.py` defines the `Portfolio` class which tracks allocations and logs trades executed by `execution.ExecutionEngine`. The engine wraps the Alpaca API and enforces basic risk checks.

Weights are rebalanced to target percentages and all trades are recorded in MongoDB collections.

## Analytics

`analytics.py` provides helper functions such as portfolio Sharpe ratio calculation and value-at-risk metrics.

## Testing

The project includes a comprehensive test suite. To run the tests:
```bash
pytest -q
```
All tests should pass without needing network access. Dummy database objects are used when the `TESTING` environment variable is set.

## Running Example

An example entry point is provided in `main.py` which demonstrates how to start a scheduler and register a sample strategy. Execute:
```bash
python main.py
```
This will load any saved portfolios from the database, schedule strategies and run indefinitely until interrupted.

