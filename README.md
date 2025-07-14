# Portfolio Allocation System

The Portfolio Allocation System is a Python service for running data-driven trading strategies.  A FastAPI server exposes REST endpoints while a background scheduler executes portfolio updates.  Data scrapers load alternative data into Postgres and DuckDB, and the execution gateway places orders through the Alpaca API.  Logging, metrics and optional distributed tracing provide full observability. Daily portfolio metrics and account snapshots are stored in Postgres for auditing.

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

**Formula**: ![Sharpe](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20S%20%3D%20\frac{\mathbb{E}[r_t]}{\sigma[r_t]}\sqrt{252})

Measures the expected excess return per unit of volatility. A higher Sharpe ratio indicates more efficient risk-adjusted performance.

### Sortino Ratio

**Formula**: ![Sortino](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20S^-\;=\;\frac{\mathbb{E}[r_t]}{\sigma[r_t\,|\,r_t<0]}\sqrt{252})

Focuses on downside deviation rather than total volatility, rewarding portfolios that avoid large losses.

### Ledoit--Wolf Covariance

**Formula**: ![LW](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20\Sigma%20%3D%20252\,\text{LW}(r_t))

Provides a shrinkage estimator for the return covariance matrix, yielding more stable risk estimates from limited data.


### Risk Parity

**Formula**: weights scaled so ![RP](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20w_i(\Sigma%20w)_i) are equal

Scales positions such that each contributes the same amount of variance, promoting diversification across assets.

### Min--Max Optimisation

**Formula**: ![MinMax](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20w^*%20%3D%20\arg\max_w\,w^\top\mu%20-%20\gamma(1%2B\delta)w^\top\Sigma%20w)

Determines portfolio weights by trading off expected return against predicted risk under current volatility conditions.

### Historical VaR

Formula:  ![VaR Formula](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20\text{VaR}_{\alpha}\;=\;-\operatorname{quantile}_{1-\alpha}(r_t))

Estimates the loss threshold not exceeded with probability $\alpha$ over the
sample distribution of returns.

### Conditional VaR

Formula: ![CVaR Formula](https://latex.codecogs.com/svg.latex?\color{white}\textstyle%20\text{CVaR}_{\alpha}\;=\;-\mathbb{E}[r_t\,|\,r_t\le-\text{VaR}_{\alpha}])

Measures the expected loss in the tail beyond the VaR level, providing a sense
of worst-case risk.
## Strategy Reference

Data sources and rebalance frequency for each strategy are shown below. The
**Key Rule** column summarises how positions are selected.

| Strategy | Source | Period | Key Rule |
|---------|--------|--------|---------|
| Congressional-Trading Aggregate | Quiver congress trading | Weekly (Mon) | Long top 20 tickers by net congressional dollar buys in the last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly (first Mon) | Mimic buys for each politician sleeve with equal weighting |
| DC Insider Score Tilt | Quiver DC Insider scores | Weekly (Mon) | Long top 30 tickers ranked by insider score |
| Government-Contracts Momentum | Quiver gov contracts | Monthly (first trading day) | Own firms with at least \$50M in new federal contracts last month |
| Corporate Insider Buying Pulse | Quiver insider filings | Weekly (Mon) | Long 25 tickers showing the strongest executive buying |
| Wikipedia Attention Surge | Wikimedia page views | Weekly (Mon) | Long top 10 S&P1500 names by page-view z-score increase |
| Wall Street Bets Buzz | Reddit API | Weekly (Mon) | Long 15 tickers with fastest rise in r/WSB mentions |
| App Reviews Hype Score | Quiver app ratings | Weekly (Mon) | Long 20 names with the biggest jump in app-review "hype" |
| Google Trends + News Sentiment | Quiver Google Trends + Finviz news | Monthly (first trading day) | Long 30 tickers with rising search interest and positive news sentiment |
| Sector Risk-Parity Momentum | Yahoo Finance | Weekly (Fri) | Rotate sector ETFs using risk-parity weights on weekly momentum |
| Leveraged Sector Momentum | Yahoo Finance | Weekly (Fri) | Momentum rotation among leveraged sector ETFs |
| Volatility-Scaled Momentum | Yahoo Finance | Weekly (Fri) | Rank stocks by 12‑month return scaled by volatility |
| Upgrade Momentum | Finviz analyst revisions | Weekly (Mon) | Tilt toward names with improving analyst revisions, smoothing turnover over 8 weeks |
| Small Cap Momentum | Various filings | Monthly | Trade small-cap stocks before catalysts, exiting after 50% gain or 3 months |
| Lobbying Growth | Quiver lobbying data | Monthly | Long 20 tickers with the largest quarter‑over‑quarter lobbying spend growth |

To create your own strategy simply add a module in `strategies/` that exposes a
`build()` coroutine returning an `EquityPortfolio`. Schedule it in
`scheduler.py` with the desired frequency and store weights in the
`portfolios` table. The strategies shipped here are fully implemented
and rely on established models; you can extend them or add your own with
minimal boilerplate.

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
- `ALLOW_LIVE` – set to `true` to enable live trading instead of paper
  The `AlpacaGateway` determines whether it is connected to a paper or live
  account by inspecting the base URL. When `ALLOW_LIVE` is enabled the
  scheduler records both the live and paper accounts so equity history remains
  separate for each environment.
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
An extra `/logs` endpoint streams the application log for debugging.

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
| Analyst Ratings | https://finviz.com/quote.ashx?t=AAPL&ty=c&p=d&b=1 |
| Finviz Stock News | https://finviz.com/news.ashx?v=3 |
| S&P 500 Constituents | https://datahub.io/core/s-and-p-500-companies/_r/-/data/constituents.csv |
| S&P 500 Index | https://finance.yahoo.com/quote/%5EGSPC |
| S&P 400 Companies | https://en.wikipedia.org/wiki/List_of_S%26P_400_companies |
| S&P 600 Companies | https://en.wikipedia.org/wiki/List_of_S%26P_600_companies |
| Russell 2000 Constituents | https://russellindexes.com/sites/us/files/indices/files/russell-2000-membership-list.csv |

### Database Tables

Scraped data is stored in these Postgres collections:

- `politician_trades`
- `lobbying`
- `wiki_views`
- `dc_insider_scores`
- `gov_contracts`
- `app_reviews`
- `google_trends`
- `reddit_mentions`
- `news_headlines`
- `analyst_ratings`
- `insider_buying`
- `sp500_index`
- `ticker_returns` – weekly returns for every tracked ticker with an `index_name` column identifying the source index
- `portfolios` – stored weights for each strategy
- `trades` – executed orders across portfolios
- `weight_history` – timestamped record of portfolio weights
- `metrics` – daily returns with ret_1d/7d/30d/3m/6m/1y/2y, Sharpe, Sortino, weekly_vol, weekly_sortino, beta, ATR, RSI, max drawdown, CAGR, win rate and other risk ratios
- `account_metrics_paper` – equity history for the paper trading account
- `account_metrics_live` – equity history for the live trading account
- `alloc_log` – optimisation diagnostics including volatility, momentum and beta for each portfolio

Ticker universes are stored in dedicated tables so the S&P 500 list remains separate
from the S&P 1500, S&P 400, S&P 600 and Russell 2000 sets. Each table is exported to CSV under
`cache/universes/` via `scrapers/universe.py`:

- `sp500_universe` – S&P 500 constituents
- `sp1500_universe` – S&P 1500 constituents
- `sp400_universe` – S&P 400 constituents
- `sp600_universe` – S&P 600 constituents
- `russell2000_universe` – Russell 2000 constituents

Below is a condensed view of the schema defined in `database/schema.sql`:

| Table | Key Columns |
|-------|-------------|
| `politician_trades` | `politician`, `ticker`, `transaction`, `amount`, `date` |
| `lobbying` | `ticker`, `client`, `amount`, `date` |
| `wiki_views` | `page`, `views`, `date` |
| `dc_insider_scores` | `ticker`, `score`, `date` |
| `gov_contracts` | `ticker`, `value`, `date` |
| `app_reviews` | `ticker`, `hype`, `date` |
| `google_trends` | `ticker`, `score`, `date` |
| `reddit_mentions` | `ticker`, `mentions`, `pos`, `neu`, `neg`, `date` |
| `analyst_ratings` | `ticker`, `rating`, `date` |
| `news_headlines` | `ticker`, `headline`, `link`, `time` |
| `insider_buying` | `ticker`, `exec`, `shares`, `date` |
| `sp500_index` | `date`, `close` |
| `ticker_returns` | `symbol`, `index_name`, `date`, `ret_7d`..`ret_5y` |
| `portfolios` | `id`, `weights` |
| `trades` | `portfolio_id`, `symbol`, `qty`, `price`, `timestamp` |
| `weight_history` | `portfolio_id`, `date`, `weights` |
| `metrics` | `portfolio_id`, `date`, `ret_1d`..`cvar`, `weekly_vol`, `weekly_sortino`, `atr_14d`, `rsi_14d` |
| `account_metrics_paper` | `id`, `timestamp`, `equity`, `last_equity` |
| `account_metrics_live` | `id`, `timestamp`, `equity`, `last_equity` |
| `sp500_universe` | `symbol` |
| `sp1500_universe` | `symbol` |
| `sp400_universe` | `symbol` |
| `sp600_universe` | `symbol` |
| `russell2000_universe` | `symbol` |

All tables enforce unique keys on their primary columns to avoid duplicate
rows from repeated scrapes. Each scraper writes with `update_one(..., upsert=True)`
so subsequent runs refresh existing records instead of creating duplicates.

The scheduler triggers `update_all_metrics` every night to calculate
daily performance for each portfolio and writes account equity with
`record_account`. These tables allow the API to serve historical
statistics and track capital over time.
Once per week `update_all_ticker_returns` computes 7‑day to 5‑year
returns for every ticker in the universe so strategies can query a
ready-made momentum dataset.

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
`fetch_lobbying_data`, `fetch_trending_wiki_views`, `fetch_dc_insider_scores`,
`fetch_gov_contracts`, `fetch_app_reviews`, `fetch_google_trends`,
`fetch_wsb_mentions`, `fetch_stock_news`, `fetch_analyst_ratings`, `fetch_insider_buying` and `fetch_sp500_history` (365 days) populate Postgres tables
(`politician_trades`, `lobbying`, `wiki_views`, `dc_insider_scores`,
`gov_contracts`, `app_reviews`, `google_trends`, `reddit_mentions`, `news_headlines`, `analyst_ratings`, `insider_buying` and
`sp500_index`).  If Postgres is unreachable an in-memory DuckDB fallback keeps
the system operational until a database connection is restored.

Each strategy then queries these raw tables to build an `EquityPortfolio` using
the analytics helpers. Risk modules scale or cap the weights before the
execution gateway sends orders to the broker. Metrics are written back so future
allocations can learn from realised performance.
`StrategyScheduler` runs nightly jobs that call `update_all_metrics` and
`record_account` so both portfolio returns and account equity are updated
daily.

### Allocation Logic

Each strategy chooses its own holdings, but the allocator decides how much
capital each one receives.  The allocation process is intentionally simple:

1. **Weekly Returns** – for every portfolio, collect twelve weeks of Friday
   closes. When fewer than four weeks are available all portfolios start with
   equal weights. Missing weeks are filled with the average of the other
   portfolios so each column has twelve observations. Extreme outliers are
   clipped using a z‑score filter so noisy spikes do not skew the analysis.
2. **Covariance** – apply a Ledoit–Wolf shrinkage estimator to the weekly
   returns.  Missing values are replaced with the average return so each
   portfolio has twelve observations.
3. **Expected Returns** – compute the mean weekly return for each portfolio.
   Excess returns are defined relative to a zero risk-free rate.
4. **Tangency Portfolio** – multiply the inverse covariance matrix by the
   expected returns to obtain weights that maximise the Sharpe ratio.  The
   portfolio is scaled to an 8 % annual volatility target and clipped to the
   allowed range.
5. **Turnover Limit** – if a portfolio’s weight changes by less than
   0.5 percentage points from last week it is left untouched to reduce trading
   costs.
6. **Anomaly Check** – if the resulting portfolio volatility exceeds 500 % or
   is not a number, the allocator falls back to last week’s weights rather than
   trading on unstable signals.
7. **Diagnostics** – every optimisation step is logged with expected returns,
   covariance estimates and the final weights so performance can be audited.

The allocator now maximises the Sharpe ratio using a tangency portfolio
constructed from recent weekly returns. This simpler approach removes the
previous Black–Litterman logic and focuses on long-term risk-adjusted growth.

