# Portfolio Allocation System

The Portfolio Allocation System is a Python service for running data-driven trading strategies.  A FastAPI server exposes REST endpoints while a background scheduler executes portfolio updates.  Data scrapers load alternative data into MongoDB and DuckDB, and the execution gateway places orders through the Alpaca API.  Logging, metrics and optional distributed tracing provide full observability.

## Technical Features

- **FastAPI Service** – async HTTP interface with token authentication
- **APScheduler** – cron-like scheduler for strategy execution
- **Alpaca Gateway** – unified wrapper around the Alpaca REST API with paper/live detection
- **MongoDB + DuckDB** – persistent storage for trades, snapshots and alt-data
- **Dynamic Scrapers** – rate limited fetchers for QuiverQuant datasets
- **Risk Models** – covariance estimation, correlation regime detection and VaR
- **Analytics** – daily statistics, Prometheus metrics and OpenTelemetry tracing

## Financial Models

Return and risk estimates feed into the allocation engine.  Let $r_t$ denote daily returns.

- **Sharpe Ratio** $\displaystyle S = \frac{\mathbb{E}[r_t]}{\sigma[r_t]}\sqrt{252}$
- **Sortino Ratio** $\displaystyle S^- = \frac{\mathbb{E}[r_t]}{\sigma[r_t\,|\,r_t<0]}\sqrt{252}$
- **Ledoit–Wolf Covariance** $\Sigma = 252\,\text{LW}(r_t)$
- **Black–Litterman Posterior**
  \[\mu = ( (\tau\Sigma)^{-1} + P^\top\Omega^{-1}P )^{-1}( (\tau\Sigma)^{-1}\pi + P^\top\Omega^{-1}Q )\]
- **Risk Parity** – weights scaled so $w_i(\Sigma w)_i$ are equal
- **Min–Max Optimisation**
  \[w^* = \arg\max_w\; w^\top\mu - \gamma(1+\delta)w^\top\Sigma w\]
- **Historical VaR** $\displaystyle \text{VaR}_\alpha=-\text{quantile}_{1-\alpha}(r_t)$
- **Conditional VaR** $\displaystyle \text{CVaR}_\alpha=-\mathbb{E}[r_t\,|\,r_t\le-\text{VaR}_\alpha]$

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

Set `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `MONGO_URI` and other variables in a `.env` file or the shell before running.

## Quickstart

Start the API with Uvicorn and launch the scheduler:

```bash
python start.py
```

APScheduler jobs rebalance portfolios according to the active strategies.  REST endpoints under `/docs` allow manual portfolio management and data collection.
