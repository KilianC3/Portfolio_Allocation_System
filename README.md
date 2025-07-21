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

## System Overview

Scrapers gather alternative datasets from QuiverQuant, Benzinga and
Wikimedia. All results are written to Postgres while a local DuckDB file
mirrors the schema so analytics can run offline. Strategies read these
tables to compute composite scores and build target weights. The
execution layer submits orders via Alpaca and records fills to the
`trades` table. Metrics and account equity are archived nightly for
performance monitoring.

## Getting Started

1. Clone the repository and create a virtual environment
   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   python3 -m venv venv
   source venv/bin/activate
   pip install -r deploy/requirements.txt
   ```
2. Edit `service/config.yaml` with your Postgres URI, Alpaca keys,
   `FRED_API_KEY` and an `API_TOKEN` that clients will use for
   authentication.
3. Run the bootstrap script to install dependencies, load all datasets
   and start the service under systemd
   ```bash
   sudo scripts/bootstrap.sh
   ```
   When the script completes the API is running on port `8001`.
4. Open the dashboard in your browser to verify the service
   ```
   http://localhost:8001/dashboard?token=<YOUR_TOKEN>
   ```
5. (Optional) install test dependencies and run the unit tests
   ```bash
   pip install -r deploy/requirements-test.txt
   pytest -q
   ```
   See `docs/AGENTS_ROOT.md` for commit conventions and repository tips.


## Strategy Reference

| Strategy | Source | Frequency | Selection Rule |
|---------|--------|-----------|----------------|
| Congressional-Trading Aggregate | Quiver congress trades | Weekly | Long 20 tickers with highest net buys last month |
| "Follow-the-Leader" Politician Sleeves | Individual congress trading pages | Monthly | Mirror buys for Pelosi, Meuser and Capito |
| DC Insider Score Tilt | Quiver DC Insider scores | Weekly | Long top 30 ranked by score |
| Government-Contracts Momentum | Quiver gov contracts | Monthly | Own firms with \$50M+ new federal contracts |
| Corporate Insider Buying Pulse | Quiver insider filings | Weekly | Long 25 tickers with strongest buying |
| Wikipedia Attention Surge | Wikimedia page views | Monthly | Long top 10 names by page‑view jump |
| Wall Street Bets Buzz | ApeWisdom API | Weekly | Long 15 tickers with fastest rise in mentions |
| App Reviews Hype Score | Quiver app ratings | Weekly | Long 20 names with largest hype increase |
| Google Trends + News Sentiment | Quiver Google Trends + Finviz news | Monthly | Long 30 tickers with rising search interest and good news |
| Sector Risk-Parity Momentum | Yahoo Finance | Weekly | Rotate sector ETFs using risk‑parity weights |
| Leveraged Sector Momentum | Yahoo Finance | Weekly | Momentum rotation among leveraged sector ETFs |
| Volatility-Scaled Momentum | Yahoo Finance | Weekly | Rank stocks by 12‑month return scaled by volatility |
| Upgrade Momentum | Benzinga upgrades | Weekly | Tilt toward names with improving analyst revisions |
| Small Cap Momentum | Various filings | Monthly | Trade small caps before catalysts, exit after 50% gain or 3 months |
| Sector-Neutral Mini-Portfolios | Composite screener | Quarterly | Equal-weight top value names by sector |
| Micro-Small Composite Leaders | Composite screener | Monthly | Value and momentum leaders in micro/small caps |
| Lobbying Growth | Quiver lobbying data | Monthly | Long 20 tickers with largest lobbying spend growth |
| Composite Score Leaders | Monthly composite rankings | Monthly | Equal-weight top 20 names by overall score |

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
| Analyst Ratings | https://www.benzinga.com/analyst-ratings/upgrades |
| Finviz Stock News | https://finviz.com/news.ashx?v=3 |
| Fundamental Scores | computed internally |
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
- `universe` – full list of tradable symbols with `index_name`
- Ticker constituents from the S&P 500, S&P 400 and Russell 2000 populate this table
- `portfolios` – stored weights for each strategy
- `trades` – executed orders
- `weight_history` – timestamped portfolio weights
- `metrics` – daily performance statistics
- `ticker_scores` – monthly composite fundamentals and momentum ranks
- `account_metrics_paper` – equity history for the paper account
- `account_metrics_live` – equity history for the live account
- `account_metrics` – point-in-time equity snapshots
- `schema_version` – schema migration tracking
- `cache` – key/value store for HTTP responses
- `alloc_log` – allocation diagnostics
- `system_logs` – structured log records for the front end
- `top_scores` – top 20 tickers by composite score each month

## Workflow

1. On startup the scrapers fetch all datasets and populate Postgres. If
   the connection fails the database layer automatically falls back to DuckDB.
2. Strategies pull data from these tables to build `EquityPortfolio` objects
   which are persisted to the `portfolios` table.
3. Risk modules cap exposures before orders are sent to Alpaca through the
   execution gateway.
4. The scheduler runs nightly to update metrics, account equity snapshots and
   ticker scores. Any failed tasks are logged in `alloc_log` for later review.

## Database Dashboard

The `/db/{table}` endpoint exposes read-only access to any table when the
correct `API_TOKEN` is supplied. A lightweight web dashboard is served at
`/dashboard` so you can inspect recent data and scheduler jobs from your
browser. Pass the API token via the `Authorization` header or a `token`
query parameter. Visit
`http://localhost:8001/dashboard?token=<YOUR_TOKEN>` after bootstrap to see
table samples. The helper script `scripts/dashboard.py` queries these
endpoints and prints the latest rows in a tabular format as a CLI view.


Run the dashboard with:

```bash
python scripts/dashboard.py
```

## API Access

Make sure the API is running on port `8001` (either from `bootstrap.sh`
or by manually starting `python -m service.start`). Authenticate each
request with your API token using the `Authorization` header or a
`token` query parameter.
The token is defined in `service/config.yaml`.

Example curl request to read the latest trades:

```bash
curl "http://localhost:8001/db/trades?limit=20&token=<YOUR_TOKEN>"
```

Example access using Python:

```python
import pandas as pd
import requests

token = "<YOUR_TOKEN>"
resp = requests.get(
    "http://localhost:8001/db/trades",
    params={"limit": 20, "token": token},
)
df = pd.DataFrame(resp.json()["records"])
print(df.head())
```

Open the dashboard in your browser at
`http://localhost:8001/dashboard?token=<YOUR_TOKEN>` to view health,
schedule information and sample rows from each table.

## Allocation Logic

Weekly returns are cleaned with a z-score filter and a rolling window of up to 36 weeks is used. When fewer than four weeks of data exist the allocator simply assigns equal weights. Once at least four weeks are available, all history up to 36 weeks feeds the Ledoit–Wolf covariance and mean-return estimates. The positive part of ``Σ⁻¹μ`` gives the long-only max‑Sharpe mix while ``Σ⁻¹(μ − r_f)`` yields the tangency portfolio. This unit-sum portfolio is scaled to an 11% volatility target (clamped between 10–12%) and clipped to the configured bounds. Tiny changes below 0.5 percentage points are skipped, extreme volatility reuses the previous allocation, and portfolio correlations and sector exposures are provided for the UI.

## Crisis Regime Detection

At each daily rebalance a Crisis Composite Indicator (CCI) is computed from several FRED macroeconomic series. The indicator sums positive z-scores weighted by importance. Position weights are multiplied by a scaling factor `S(CCI)`:

```
S(CCI) = 1.0                       if CCI < 1.0
S(CCI) = 1.0 - 0.3 * (CCI - 1.0)   if 1.0 ≤ CCI < 2.0
S(CCI) = max(0.3, 0.7 - 0.4 * (CCI - 2.0)) otherwise
```

This reduces exposure during stressed regimes while keeping full allocation in calm markets.

