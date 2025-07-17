# Portfolio Allocation System

The Portfolio Allocation System runs a suite of alternative‑data strategies and exposes a REST API for automated trading.  Scrapers ingest public data into Postgres, strategies produce target weights and the execution gateway sends orders through Alpaca.  Metrics and logs are stored so performance can be reviewed at any time.

## Key Features

- **FastAPI service** with token authentication
- **APScheduler** for scheduled rebalances
- **Alpaca** gateway with paper/live detection
- **Postgres + DuckDB** data store
- **Prometheus metrics** and structured logging
- **Correlation endpoint** to compare portfolio relationships
- **Sector exposure endpoint** for portfolio sector breakdowns

## Usage

1. Clone the repository and create a virtual environment
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   python3 -m venv venv
   source venv/bin/activate
   pip install -r deploy/requirements.txt
   ```
2. Create the Postgres user and database referenced in `service/config.yaml`.
3. Edit `service/config.yaml` with your Alpaca keys, Postgres URI and optional API token.
4. Start the service which launches the API, scheduler and all scrapers
   ```bash
   python -m service.start
   ```
   The startup script now runs each scraper in sequence and logs a checklist
   once data is loaded.
5. Install the optional test dependencies and run the unit tests
   ```bash
   pip install -r deploy/requirements-test.txt
   pytest -q
   ```
   See `docs/AGENTS_ROOT.md` for commit guidelines and environment details.

## Strategy Reference

| Strategy | Source | Frequency | Selection Rule |
|---------|--------|-----------|----------------|
| Congressional-Trading Aggregate | Quiver congress trades | Weekly | Long 20 tickers with highest net buys last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly | Mirror buys for Pelosi, Meuser and Capito |
| DC Insider Score Tilt | Quiver DC Insider scores | Weekly | Long top 30 ranked by score |
| Government-Contracts Momentum | Quiver gov contracts | Monthly | Own firms with \$50M+ new federal contracts |
| Corporate Insider Buying Pulse | Quiver insider filings | Weekly | Long 25 tickers with strongest buying |
| Wikipedia Attention Surge | Wikimedia page views | Weekly | Long top 10 names by page‑view jump |
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
| Finviz Fundamentals | https://finviz.com/quote.ashx?t=AAPL&p=d&ty=ea |
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
- `universe` – full list of tradable symbols with `index_name` and composite scores
- Ticker constituents from the S&P 500, S&P 400 and Russell 2000 populate this table
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

Weekly returns are cleaned with a z-score filter and a rolling window of up to 36 weeks is used. When fewer than four weeks of data exist the allocator simply assigns equal weights. Once at least four weeks are available, all history up to 36 weeks feeds the Ledoit–Wolf covariance and mean-return estimates. The positive part of ``Σ⁻¹μ`` gives the long-only max‑Sharpe mix while ``Σ⁻¹(μ − r_f)`` yields the tangency portfolio. This unit-sum portfolio is scaled to an 11% volatility target (clamped between 10–12%) and clipped to the configured bounds. Tiny changes below 0.5 percentage points are skipped, extreme volatility reuses the previous allocation, and portfolio correlations and sector exposures are provided for the UI.

