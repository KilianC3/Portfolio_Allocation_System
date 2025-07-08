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

**Formula**: $\displaystyle \text{VaR}_\alpha=-\text{quantile}_{1-\alpha}(r_t)$

Estimates the threshold loss not exceeded with probability $\alpha$ over the sample distribution of returns.

### Conditional VaR

**Formula**: $\displaystyle \text{CVaR}_\alpha=-\mathbb{E}[r_t\,|\,r_t\le-\text{VaR}_\alpha]$

Measures the average loss in the tail beyond the VaR level, providing a sense of worst-case risk.
## Strategy Reference

Data sources and rebalance frequency for each strategy are shown below.

| Strategy | Source | Period | Description |
|---------|--------|--------|-------------|
| Congressional-Trading Aggregate | Quiver congress trading | Weekly (Mon) | Top 20 names by net congressional dollar buys over the last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly (first Mon) | Replicate trades for specific politicians |
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

Set `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `PG_URI` and other variables in a `.env` file or the shell before running.

## Quickstart

Start the API with Uvicorn and launch the scheduler:

```bash
python start.py
```

APScheduler jobs rebalance portfolios according to the active strategies.  REST endpoints under `/docs` allow manual portfolio management and data collection.

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

Data from the various scrapers is inserted into Postgres during startup. Each
strategy queries these raw tables to build an `EquityPortfolio` using the
analytics helpers. Risk modules then scale or cap the weights before the
execution gateway sends orders to the broker. Metrics are written back to the
database so future allocations can learn from realised performance.

### Allocation Logic

Every strategy ultimately produces a vector of expected returns `\mu` and a
covariance matrix `\Sigma`. The allocation engine solves a min--max problem
that balances return against predicted risk:

$$w^* = \arg\max_w\; w^\top \mu - \gamma(1+\delta) w^\top \Sigma w$$

where `\gamma` represents overall risk aversion and `\delta` reflects current
volatility regime. The resulting weights are normalised and passed through the
risk-parity module so that each position contributes equally to portfolio
volatility. Combined with the Black--Litterman adjustments described above, this
framework aims to generate maximum risk-adjusted returns across all strategies.
