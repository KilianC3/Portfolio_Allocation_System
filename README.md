# Portfolio Allocation System

The Portfolio Allocation System is a Python service for running data-driven trading strategies.  A FastAPI server exposes REST endpoints while a background scheduler executes portfolio updates.  Data scrapers load alternative data into Postgres and DuckDB, and the execution gateway places orders through the Alpaca API.  Logging, metrics and optional distributed tracing provide full observability.

## Technical Features

- **FastAPI Service** – async HTTP interface with token authentication
- **APScheduler** – cron-like scheduler for strategy execution
- **Alpaca Gateway** – unified wrapper around the Alpaca REST API with paper/live detection
- **Postgres + DuckDB** – persistent storage for trades, snapshots and alt-data
- **Dynamic Scrapers** – rate limited fetchers for QuiverQuant datasets
- **Risk Models** – covariance estimation, correlation regime detection and VaR
- **Analytics** – daily statistics, Prometheus metrics and OpenTelemetry tracing

## Financial Models

Return and risk estimates feed into the allocation engine.  Let $r_t$ denote daily returns.


### Sharpe Ratio

**Formula**: $\displaystyle S = \frac{\mathbb{E}[r_t]}{\sigma[r_t]}\sqrt{252}$

Measures the expected excess return per unit of volatility. A higher Sharpe ratio indicates more efficient risk-adjusted performance.

### Sortino Ratio

**Formula**: $\displaystyle S^- = \frac{\mathbb{E}[r_t]}{\sigma[r_t\,|\,r_t<0]}\sqrt{252}$

Focuses on downside deviation rather than total volatility, rewarding portfolios that avoid large losses.

### Ledoit--Wolf Covariance

**Formula**: $\Sigma = 252\,\text{LW}(r_t)$

Provides a shrinkage estimator for the return covariance matrix, yielding more stable risk estimates from limited data.

### Black--Litterman Posterior

**Formula**: $\mu = ((\tau\Sigma)^{-1} + P^\top\Omega^{-1}P)^{-1}\big((\tau\Sigma)^{-1}\pi + P^\top\Omega^{-1}Q\big)$

Combines market equilibrium returns with subjective views to produce a balanced forecast of expected returns.

### Risk Parity

**Formula**: weights scaled so $w_i(\Sigma w)_i$ are equal

Scales positions such that each contributes the same amount of variance, promoting diversification across assets.

### Min--Max Optimisation

**Formula**: $w^* = \arg\max_w\; w^\top\mu - \gamma(1+\delta)w^\top\Sigma w$

Determines portfolio weights by trading off expected return against predicted risk under current volatility conditions.

### Historical VaR

Formula:  ![VaR Formula](https://latex.codecogs.com/svg.latex?%5Ctext%7BVaR%7D_%5Calpha%20%3D%20-%5Coperatorname%7Bquantile%7D_%7B1-%5Calpha%7D%28r_t%29)

Estimates the loss threshold not exceeded with probability $\alpha$ over the
sample distribution of returns.

### Conditional VaR

Formula: ![CVaR Formula](https://latex.codecogs.com/svg.latex?%5Ctext%7BCVaR%7D_%5Calpha%20%3D%20-%5Cmathbb%7BE%7D%5Br_t%20%7C%20r_t%20%5Cle%20-%5Ctext%7BVaR%7D_%5Calpha%5D)

Measures the expected loss in the tail beyond the VaR level, providing a sense
of worst-case risk.
## Strategy Reference

Data sources and rebalance frequency for each strategy are shown below.

| Strategy | Source | Period | Description |
|---------|--------|--------|-------------|
| Congressional-Trading Aggregate | Quiver congress trading | Weekly (Mon) | Top 20 names by net congressional dollar buys over the last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly (first Mon) | Replicate trades for specific politicians (e.g. Nancy Pelosi, Dan Meuser, Shelley Moore Capito) |
| DC Insider Score Tilt | Quiver DC Insider scores | Weekly (Mon) | Long the 30 highest insider-score stocks |
| Government-Contracts Momentum | Quiver gov contracts | Monthly (first trading day) | Own firms with ≥\$50M in new federal contracts last month |
| Corporate Insider Buying Pulse | Quiver insider filings | Weekly (Mon) | Long the 25 tickers with strongest executive buying |
| Wikipedia Attention Surge | Wikimedia page views | Weekly (Mon) | Long the 10 S&P1500 stocks with the biggest page-view spike |
| Wall Street Bets Buzz | Reddit API | Weekly (Mon) | Long the 15 symbols with the fastest rise in subreddit mentions |
| App Reviews Hype Score | Quiver app ratings | Weekly (Mon) | Long the 20 names with the largest jump in app-review "hype" |
| Google Trends + News Sentiment | Quiver Google Trends | Monthly (first trading day) | Long 30 tickers with rising search interest and positive news |
| Sector Risk-Parity Momentum | Yahoo Finance | Weekly (Fri) | Rotate among sector ETFs using risk-parity weights |
| Leveraged Sector Momentum | Yahoo Finance | Weekly (Fri) | Momentum rotation among leveraged sector ETFs |
| Volatility-Scaled Momentum | Yahoo Finance | Weekly (Fri) | Rank stocks by 12‑month return scaled by volatility |
| Upgrade Momentum | Quiver analyst ratings | Weekly (Mon) | Tilt toward names with a surge in upgrades |
| Biotech Binary Event Basket | Various filings | Monthly | Basket of biotech stocks ahead of binary catalysts |
| Lobbying Growth | Quiver lobbying data | Monthly | Long the 20 tickers with the largest quarter‑over‑quarter lobbying spend growth |

## Installation

1. Clone the repository
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   ```
2. Create and activate a virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install Python dependencies
   ```bash
   pip install -r requirements.txt
   ```
   For a lightweight test setup you can instead use `requirements-test.txt`:
   ```bash
   pip install -r requirements-test.txt
   ```

### Configuration

Application settings live in `config.py`. Values are loaded from
`config.yaml` if that file exists, falling back to environment variables.
The file is parsed with a lightweight built-in helper so no external YAML
package is required.
Edit `config.yaml` with your own credentials:

- `ALPACA_API_KEY` and `ALPACA_API_SECRET` – credentials for the Alpaca API
- `ALPACA_BASE_URL` – broker endpoint (`https://paper-api.alpaca.markets` by default)
- `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` – Reddit API keys for the WSB scraper
- `PG_URI` – Postgres connection string, e.g. `postgresql://user:pass@localhost:5432/quant_fund`
- `API_TOKEN` – optional bearer token protecting REST endpoints

The `config.py` module also exposes defaults such as rate limits and schedule
definitions, providing type-checked access to all fields.

## Quickstart

Start the API with Uvicorn on port 8001 and launch the scheduler:

```bash
python start.py
```
The API listens on `http://localhost:8001`.
The provided Dockerfile runs this same command so container deployments
start the service automatically.

APScheduler jobs rebalance portfolios according to the active strategies.  REST endpoints under `/docs` allow manual portfolio management and data collection.

To preload all datasets without launching the API run:

```bash
python -m scripts.bootstrap
```

Check overall system status at any time with:

```bash
python -m scripts.health_check
```

### Scraper URLs

The system fetches alternative data from the following sources:

| Dataset | URL |
|---------|-----|
| DC Insider Scores | https://www.quiverquant.com/scores/dcinsider |
| Corporate Lobbying | https://www.quiverquant.com/lobbying/ |
| Government Contracts | https://www.quiverquant.com/sources/govcontracts |
| Politician Trading | https://www.quiverquant.com/congresstrading/ |
| App Reviews | https://www.quiverquant.com/sources/appratings |
| Google Trends | https://www.quiverquant.com/googletrends/ |
| Insider Buying | https://www.quiverquant.com/insiders/ |
| Wikipedia Views | https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{Page_Title}/daily/{start}/{end} |
| Analyst Ratings | *custom provider* |
| S&P 500 Constituents | https://datahub.io/core/s-and-p-500-companies/_r/-/data/constituents.csv |
| S&P 500 Index | https://finance.yahoo.com/quote/%5EGSPC |
| S&P 400 Companies | https://en.wikipedia.org/wiki/List_of_S%26P_400_companies |
| S&P 600 Companies | https://en.wikipedia.org/wiki/List_of_S%26P_600_companies |
| Russell 2000 Constituents | https://russellindexes.com/sites/us/files/indices/files/russell-2000-membership-list.csv |

### Running in an LXC Container

The system can run inside a lightweight Ubuntu container:

1. Launch and enter the container
   ```bash
   lxc launch images:ubuntu/22.04 portfolio-box
   lxc exec portfolio-box -- bash
   ```
2. Install system packages
   ```bash
   apt update && apt install -y git python3-venv postgresql
   ```
3. Create a Postgres user and database
   ```bash
   sudo -u postgres createuser --password portfolio
   sudo -u postgres createdb -O portfolio quant_fund
   ```
   The connection string is then:
   `postgresql://portfolio:<password>@localhost:5432/quant_fund`
4. Follow the [Installation](#installation) steps inside the container and update
   `config.yaml` with the PG_URI from above.

## Repository Structure

The project is organised into logical packages:

- `analytics/` – portfolio statistics and optimisation utilities
- `core/` – portfolio objects and shared dataclasses
- `database/` – Postgres helpers and collections
- `execution/` – order gateways and broker abstractions
- `infra/` – scraping helpers and rate limiters
- `scrapers/` – data collection scripts
- `strategies/` – trading strategies built on the analytics layer
- `tests/` – unit tests for all modules

## Further Documentation

Additional guides live in the [`docs/`](docs/index.md) folder which is rendered with MkDocs.

## System Workflow

When the API starts it triggers all scrapers once so that required datasets are
available immediately.  The functions `fetch_politician_trades`,
`fetch_lobbying_data`, `fetch_wiki_views`, `fetch_dc_insider_scores`,
`fetch_gov_contracts`, `fetch_app_reviews`, `fetch_google_trends`,
`fetch_insider_buying` and `fetch_sp500_history` populate Postgres tables
(`politician_trades`, `lobbying`, `wiki_views`, `dc_insider_scores`,
`gov_contracts`, `app_reviews`, `google_trends`, `insider_buying` and
`sp500_index`).  If Postgres is unreachable an in-memory DuckDB fallback keeps
the system operational until a database connection is restored.

Each strategy then queries these raw tables to build an `EquityPortfolio` using
the analytics helpers. Risk modules scale or cap the weights before the
execution gateway sends orders to the broker. Metrics are written back so future
allocations can learn from realised performance.

### Allocation Logic

Every strategy ultimately produces a vector of expected returns `\mu` and a
covariance matrix `\Sigma`. The analytics layer applies the models listed above:
Sharpe and Sortino ratios inform expected returns, Ledoit--Wolf shrinkage
estimates covariance, Black--Litterman views adjust the forecasts, and
VaR/CVaR metrics bound the risk budget. The allocation engine then solves a
min--max problem that balances return against predicted risk:

$$w^* = \arg\max_w\; w^\top \mu - \gamma(1+\delta) w^\top \Sigma w$$

where `\gamma` represents overall risk aversion and `\delta` reflects current
volatility regime. The resulting weights are normalised and passed through the
risk-parity module so that each position contributes equally to portfolio
volatility. Combined with the Black--Litterman and risk measures noted above,
this framework aims to generate maximum risk-adjusted returns across all
strategies.
