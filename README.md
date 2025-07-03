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
- `QUIVER_RATE_SEC` – seconds between scraper requests (default `1.1`).
- `MONGO_URI` – MongoDB connection URI (default `mongodb://localhost:27017`).
- `DB_NAME` – MongoDB database name (default `quant_fund`).
- `MIN_ALLOCATION` and `MAX_ALLOCATION` – portfolio weight bounds.

## Running the API

Start the FastAPI server with Uvicorn:
```bash
uvicorn api:app --reload
```
The API exposes JSON endpoints to manage portfolios, trigger scrapers and check
scheduled jobs. It is designed to be consumed by a web front end in the future
without further changes to the backend. See `api.py` for full route definitions.

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
Daily performance data can be posted to the `/metrics/{pf_id}` endpoint. The API
automatically updates trailing statistics such as Sharpe, Sortino, alpha, beta,
tracking error and drawdown for each portfolio. These metrics feed directly into
the allocation engine.

## Scrapers

Modules in `scrapers/` fetch datasets from QuiverQuant. Each function returns a list of records and stores them in the database:

- `politician.py` – congressional trading disclosures
- `lobbying.py` – corporate lobbying spending
- `wiki.py` – Wikipedia page view statistics
- `dc_insider.py` – insider sentiment and investor scores
- `gov_contracts.py` – government contract awards

Scrapers share a simple caching mechanism via `infra.smart_scraper.get` and respect rate limits using `infra.rate_limiter.AsyncRateLimiter`.

## Portfolio Management

`core/portfolio.py` provides an abstract `Portfolio` base class. `core/equity.py` implements an `EquityPortfolio` using an execution gateway. The default gateway `AlpacaGateway` wraps Alpaca's REST API and applies basic risk checks.

Weights are rebalanced to target percentages and all trades are recorded in MongoDB collections. Because Alpaca accounts do not support sub-portfolios, each order is tagged using `client_order_id` with the portfolio's identifier. Positions for a portfolio can be queried via the `/positions/{pf_id}` endpoint which aggregates executed trades.

`Portfolio.rebalance` now closes stale positions as new weights are applied and leverages stored trade history rather than account-wide positions, ensuring clean separation between multiple portfolios hosted on the same Alpaca account.

## Risk Management

The new `risk` package calculates exposures, historical VaR and provides a simple `CircuitBreaker` to halt trading after large losses. These utilities operate on the master ledger stored in MongoDB and can be extended for additional controls.

## Analytics

`analytics.py` now exposes a wide range of statistics including Sharpe, Sortino,
alpha, beta, tracking error, information ratio and maximum drawdown. The
`allocation_engine.compute_weights` routine combines these measures to size
portfolios dynamically while respecting volatility targets. Rebalancing jobs use
the latest scraped data and stored returns so that portfolio adjustments do not
introduce any look-ahead bias.

## Running Example

An example entry point is provided in `main.py` which demonstrates how to start a scheduler and register a sample strategy. Execute:
```bash
python main.py
```
This will load any saved portfolios from the database, schedule strategies and run indefinitely until interrupted.

