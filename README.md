# Portfolio Allocation System

This project implements a minimal portfolio management API and scraping suite built with Python. It provides tools to schedule trading strategies, collect alternative data and record trades in a MongoDB database.

Key features include:
- Dynamic rate limiting with exponential backoff for all scrapers
- Rolling correlation regime detection using a Gaussian mixture model
- Robust portfolio optimisation with optional min–max solver
- Scheduler that can be started or stopped via API or `AUTO_START_SCHED`
- Safety checks for Alpaca paper vs live trading endpoints
- Continuous analytics for each strategy and overall account equity
- Optional API token authentication and real-time SSE/WebSocket streams

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
- `ALPACA_BASE_URL` – API endpoint (default `https://paper-api.alpaca.markets`). Use the paper URL for testing and the live URL only when ready to trade.
- `QUIVER_RATE_SEC` – seconds between scraper requests (default `1.1`).
- `MONGO_URI` – MongoDB connection URI (default `mongodb://localhost:27017`).
- `DB_NAME` – MongoDB database name (default `quant_fund`).
- `MIN_ALLOCATION` and `MAX_ALLOCATION` – portfolio weight bounds.
- `LOG_LEVEL` – logging verbosity (default `INFO`).
- `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` – credentials for the Reddit API.
- `REDDIT_USER_AGENT` – identifier string for Reddit requests (default `WSB-Strategy/1.0`).
- `AUTO_START_SCHED` – set to `true` to launch the scheduler automatically when
  the API starts. Otherwise call `/scheduler/start` once ready to trade.
- `API_TOKEN` – if set, all endpoints require `Authorization: Bearer <token>`.

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
sched.start()  # or call `/scheduler/start` via the API
```
The scheduler also runs a weekly rebalancing job that uses metrics stored in MongoDB to compute new allocations via `allocation_engine.compute_weights`. When finished trading you can stop all jobs with `/scheduler/stop`.
Daily performance data can be posted to the `/metrics/{pf_id}` endpoint. The API
automatically updates trailing statistics such as Sharpe, Sortino, alpha, beta,
tracking error and drawdown for each portfolio. These metrics feed directly into
the allocation engine. You can refresh statistics for all portfolios with
`/collect/metrics`, which downloads latest prices and updates each portfolio's
metrics even when no positions are held. A daily scheduler task calls this
endpoint automatically so strategy analytics are always captured even if the
portfolio is inactive.

## Scrapers

Modules in `scrapers/` fetch datasets from QuiverQuant. Each function returns a list of records and stores them in the database:

- `politician.py` – congressional trading disclosures
- `lobbying.py` – corporate lobbying spending
- `wiki.py` – Wikipedia page view statistics
- `dc_insider.py` – insider sentiment and investor scores
- `gov_contracts.py` – government contract awards

Scrapers share a simple caching mechanism via `infra.smart_scraper.get` and now
use a dynamic rate limiter with exponential backoff
(`infra.rate_limiter.DynamicRateLimiter`). This adapts to transient 429 responses
so scraping continues smoothly under heavy load.

## Data Store

All scraped records are normalised into a DuckDB database at `data/altdata.duckdb` in
addition to MongoDB. Each scraper appends its table so historical snapshots are
versioned automatically. See [docs/data_format.md](docs/data_format.md) for the list
of tables and columns.

## Portfolio Management

`core/portfolio.py` provides an abstract `Portfolio` base class. `core/equity.py` implements an `EquityPortfolio` using an execution gateway. The default gateway `AlpacaGateway` wraps Alpaca's REST API and applies basic risk checks.

`AlpacaGateway` automatically detects whether the configured endpoint is the paper trading API. When a live endpoint is used you must pass `allow_live=True` to its constructor, preventing accidental real-money trades.
It also exposes an `account()` method to obtain equity information for both paper and live accounts.

Weights are rebalanced to target percentages and all trades are recorded in MongoDB collections. Because Alpaca accounts do not support sub-portfolios, each order is tagged using `client_order_id` with the portfolio's identifier. Positions for a portfolio can be queried via the `/positions/{pf_id}` endpoint which aggregates executed trades.
Individual positions can be closed via `POST /close/{pf_id}/{symbol}` which removes the symbol from the weight set and issues an order to exit.

`Portfolio.rebalance` now closes stale positions as new weights are applied and leverages stored trade history rather than account-wide positions, ensuring clean separation between multiple portfolios hosted on the same Alpaca account.

## Risk Management

The `risk` package includes dynamic correlation regime detection. Rolling
correlations are fed into a Gaussian mixture model to spot regime shifts. During
high-correlation crises the allocation engine automatically de-leverages.
Existing utilities still calculate exposures, historical VaR and offer a
`CircuitBreaker` to halt trading after large losses. Covariance estimates use
Ledoit–Wolf shrinkage by default with an optional min–max solver to guard
against estimation error.

## Analytics

`analytics_utils.py` now exposes a wide range of statistics including Sharpe, Sortino,
alpha, beta, tracking error, information ratio and maximum drawdown. The
`allocation_engine.compute_weights` routine combines these measures to size
portfolios dynamically while respecting volatility targets. Rebalancing jobs use
the latest scraped data and stored returns so that portfolio adjustments do not
introduce any look-ahead bias.

Account-level equity is also recorded daily. The scheduler calls
`record_account` which stores equity and last equity for the configured
Alpaca account, distinguishing between paper and live trading URLs.

## Running Example

An example entry point is provided in `start.py` which launches both the API server and scheduler. Execute:
```bash
python start.py
```
This will load any saved portfolios from the database and run until interrupted.

### Key API Endpoints

- `GET /portfolios` – list existing portfolios
- `POST /portfolios` – create a new portfolio
- `PUT /portfolios/{id}/weights` – update target weights
- `POST /portfolios/{id}/rebalance` – place trades to match weights
- `GET /positions/{id}` – current holdings
- `POST /scheduler/start` and `POST /scheduler/stop` – control the allocation scheduler
- `POST /close/{id}/{symbol}` – close a single position
- `GET /metrics/{id}` – historical returns and statistics
- `GET /var?start=&end=` – portfolio VaR and CVaR over a date range
- `GET /correlations?start=&end=` – return correlation matrix of portfolio returns
- `GET /stream/account` – server-sent events stream of account equity
## Quickstart

1. Launch a local MongoDB instance and optional Redis server:
   ```bash
   docker run -d --name mongo -p 27017:27017 mongo:7
   docker run -d --name redis -p 6379:6379 redis:7
   ```
2. Set the required environment variables or edit `.env`.
3. Run scrapers to populate the data store:
   ```bash
   python -m scrapers.politician
   python -m scrapers.lobbying
   python -m scrapers.wiki
   python -m scrapers.dc_insider
   python -m scrapers.gov_contracts
   ```
   Each run appends rows to `data/altdata.duckdb` and MongoDB collections.
4. Start the API server with Uvicorn as shown above. The `/health` endpoint reports service status and `/metrics` exposes Prometheus data. The `/analytics/{portfolio}` endpoint returns rolling statistics computed from the stored snapshots.

## Strategy Reference

The table below lists the data sources used by each strategy and how often each portfolio is rebalanced.

| Strategy | URL(s) | Rebalance Period | One-line description |
|---------|-------|------------------|---------------------|
| Congressional-Trading Aggregate | https://www.quiverquant.com/congresstrading/ | Weekly (Mon) | Hold the 20 stocks with the largest net congressional dollar-buys over the last 30 days. |
| "Follow-the-Leader" Politician Sleeves | Meuser https://www.quiverquant.com/congresstrading/politician/Daniel%20Meuser-M001204 \| Pelosi https://www.quiverquant.com/congresstrading/politician/Nancy%20Pelosi-P000197 \| Capito https://www.quiverquant.com/congresstrading/politician/Shelley%20Moore%20Capito-C001047 | Monthly (first Mon) | Each sleeve mimics the politician’s entire set of disclosed trades. |
| DC Insider Score Tilt | https://www.quiverquant.com/scores/dcinsider | Weekly (Mon) | Go long the 30 highest "DC Insider"-scored stocks. |
| Government-Contracts Momentum | https://www.quiverquant.com/sources/govcontracts | Monthly (first trading day) | Own every firm (max 25) awarded ≥ $50 M in new U.S. federal contracts in the prior month. |
| Corporate Insider Buying Pulse | https://www.quiverquant.com/insiders/ | Weekly (Mon) | Hold the 25 names with the largest 30-day net executive dollar-buying. |
| Wikipedia Attention Surge | https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{Page_Title}/daily/{start}/{end} | Weekly (Mon) | Long the 10 S&P 1500 stocks showing the biggest spike in Wikipedia page views (7 d vs 30 d z-score). |
| Wall Street Bets Buzz | Reddit API (r/wallstreetbets) | Weekly (Mon) | Go long the 15 symbols with the fastest 7-day growth in subreddit mentions (≥ 500 baseline). |
| App Reviews Hype Score | https://www.quiverquant.com/sources/appratings | Weekly (Mon) | Own the 20 stocks with the largest week-over-week rise in Quiver’s app-review “hype score.” |
| Google Trends + News Sentiment | https://www.quiverquant.com/googletrends/ | Monthly (first trading day) | Hold the 30 tickers with the biggest month-over-month search-interest jump and positive news sentiment. |


| Sector Risk-Parity Momentum | Yahoo Finance | Weekly (Fri) | Rotate among S&P 500 sector ETFs using risk-parity weights. |
| Leveraged Sector Momentum | Yahoo Finance | Weekly (Fri) | Momentum rotation among leveraged sector ETFs. |
| Volatility-Scaled Momentum | Yahoo Finance | Weekly (Fri) | Rank stocks by twelve-month return scaled by volatility. |
| Upgrade Momentum | Quiver Analyst Ratings | Weekly (Mon) | Tilt towards names with a surge in analyst upgrades. |
| Biotech Binary Event Basket | Various filings | Monthly | Basket of biotech stocks ahead of binary catalysts. |
| Lobbying Growth (example) | Quiver Lobbying | Monthly | Placeholder using companies with strong lobbying growth. |
## Deployment on Ubuntu

Below is a step-by-step guide to running the system on an Ubuntu server. These steps assume a fresh VM with Python 3.12 installed.

1. **Install system packages**
   ```bash
   sudo apt update && sudo apt install -y git python3-venv
   ```
2. **Clone the repository**
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   ```
3. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install Python requirements**
   ```bash
   pip install -r requirements.txt
   ```
5. **Set environment variables**
   Create a `.env` file or export variables in your shell:
   ```bash
   export ALPACA_API_KEY="<key>"
   export ALPACA_API_SECRET="<secret>"
   export MONGO_URI="mongodb://localhost:27017"
   export DB_NAME="quant_fund"
   export QUIVER_RATE_SEC="1.1"
   ```
   If using Alpaca paper trading ensure `ALPACA_BASE_URL=https://paper-api.alpaca.markets`.

6. **Start MongoDB** (and optionally Redis)
   ```bash
   docker run -d --name mongo -p 27017:27017 mongo:7
   ```

7. **Run scrapers** to populate the database. Each scraper can be executed manually or via cron:
   ```bash
   python -m scrapers.politician
   python -m scrapers.lobbying
   python -m scrapers.wiki
   python -m scrapers.dc_insider
   python -m scrapers.gov_contracts
   ```
8. **Launch the server**
   ```bash
   python start.py > logs/app.log 2>&1 &
   ```
   Visit `http://your-server:8000/docs` to confirm it is running. All requests
   are CORS enabled so a future front end can consume the API directly.

9. *(Optional)* **Expose with Cloudflare Tunnel**
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   This hides your IP while still allowing secure access through a public URL.

10. **Check logs for errors**
    - `logs/app.log` collects both API and scheduler messages
    - Use `tail -f logs/app.log` to monitor activity in real time

Databases and required collections are created automatically on first run.

11. **Stopping services**
    Use `pkill -f uvicorn` and `pkill -f start.py` or stop the processes via systemd if you create service files.

### Potential Pitfalls
- Ensure system time is synced (use `timedatectl status`). Time drift can break signing for Alpaca requests.
- The Alpaca account must have sufficient buying power and permissions for the target assets.
- Network hiccups or API rate limits may cause scrapers to retry slowly; monitor logs for repeated warnings.
- MongoDB volume can grow quickly. Set up periodic backups or prune old scrapings if disk space is limited.
- If environment variables are missing the application may start but fail silently when calling external APIs.

The `AlpacaGateway` in `execution/gateway.py` is functional but minimal. Orders are submitted via Alpaca's REST API with basic notional and volume checks. Review this code and set appropriate API keys before using real money.
