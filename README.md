# Portfolio Allocation System

The Portfolio Allocation System runs a suite of alternative‑data strategies and exposes a REST API for automated trading.  Scrapers ingest public data into Postgres, strategies produce target weights and the execution gateway sends orders through Alpaca.  Metrics and logs are stored so performance can be reviewed at any time.

## Key Features

- **FastAPI service** with token authentication
- **APScheduler** for scheduled rebalances
- **Alpaca** gateway with paper/live detection
- **Postgres + DuckDB** data store
- **Prometheus metrics** and structured logging

## Usage

1. Clone the repository and create a virtual environment
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Edit `config.yaml` with your Alpaca keys, Postgres URI and optional API token.
3. Start the service which launches the API and scheduler
   ```bash
   python start.py
   ```
   Use `python -m scripts.bootstrap` if you want to seed all datasets first.

## Strategy Reference

| Strategy | Source | Frequency | Selection Rule |
|---------|--------|-----------|----------------|
| Congressional-Trading Aggregate | Quiver congress trades | Weekly | Long 20 tickers with highest net buys last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly | Mirror buys for Pelosi, Meuser and Capito |
| DC Insider Score Tilt | Quiver DC Insider scores | Weekly | Long top 30 ranked by score |
| Government-Contracts Momentum | Quiver gov contracts | Monthly | Own firms with \$50M+ new federal contracts |
| Corporate Insider Buying Pulse | Quiver insider filings | Weekly | Long 25 tickers with strongest buying |
| Wikipedia Attention Surge | Wikimedia page views | Weekly | Long top 10 S&P1500 names by page‑view jump |
| Wall Street Bets Buzz | Reddit API | Weekly | Long 15 tickers with fastest rise in mentions |
| App Reviews Hype Score | Quiver app ratings | Weekly | Long 20 names with largest hype increase |
| Google Trends + News Sentiment | Quiver Google Trends + Finviz news | Monthly | Long 30 tickers with rising search interest and good news |
| Sector Risk-Parity Momentum | Yahoo Finance | Weekly | Rotate sector ETFs using risk‑parity weights |
| Leveraged Sector Momentum | Yahoo Finance | Weekly | Momentum rotation among leveraged sector ETFs |
| Volatility-Scaled Momentum | Yahoo Finance | Weekly | Rank stocks by 12‑month return scaled by volatility |
| Upgrade Momentum | Finviz analyst revisions | Weekly | Tilt toward names with improving analyst revisions |
| Small Cap Momentum | Various filings | Monthly | Trade small caps before catalysts, exit after 50% gain or 3 months |
| Lobbying Growth | Quiver lobbying data | Monthly | Long 20 tickers with largest lobbying spend growth |

## Data Sources

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
| S&P 500 Index | https://finance.yahoo.com/quote/%5EGSPC |

## Database Tables

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
- `universe` – full list of tradable symbols with `index_name`, recent returns and metrics
- `portfolios` – stored weights for each strategy
- `trades` – executed orders
- `weight_history` – timestamped portfolio weights
- `metrics` – daily performance statistics
- `account_metrics_paper` – equity history for the paper account
- `account_metrics_live` – equity history for the live account
- `alloc_log` – allocation diagnostics

## Workflow

1. On startup the scrapers fetch all datasets and populate Postgres.
2. Strategies pull data from these tables to build `EquityPortfolio` objects.
3. Risk modules cap exposures before orders are sent to Alpaca.
4. The scheduler runs nightly to update metrics and account equity.

## Allocation Logic

Weekly returns for each portfolio are cleaned with a z‑score filter and summarised over the last twelve weeks. A Ledoit–Wolf estimator produces the covariance matrix and mean returns are treated as expected returns. The tangency portfolio weights are computed from these inputs, scaled to an 8% annual volatility target and clipped to the configured minimum and maximum. Small changes under 0.5 percentage points are ignored to reduce turnover. If the resulting volatility is unrealistic, the previous weights are reused. Every step is logged for audit purposes.

