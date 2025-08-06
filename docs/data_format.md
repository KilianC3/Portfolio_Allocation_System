# Data Store Format

Scrapers normalise the raw HTML tables from QuiverQuant into columnar snapshots stored in MariaDB.
Each table contains all historical rows appended with a `_retrieved` timestamp so later
analysis can reproduce past views of the data.

## Tables and Columns

| Table | Columns |
|-------|---------|
| `politician_trades` | `politician`, `ticker`, `transaction`, `amount`, `date`, `_retrieved` |
| `lobbying` | `ticker`, `client`, `amount`, `date`, `_retrieved` |
| `wiki_views` | `ticker`, `views`, `date`, `_retrieved` |
| `dc_insider_scores` | `ticker`, `score`, `date`, `_retrieved` |
| `gov_contracts` | `ticker`, `value`, `date`, `_retrieved` |
| `app_reviews` | `ticker`, `hype`, `date`, `_retrieved` |
| `google_trends` | `ticker`, `score`, `date`, `_retrieved` |
| `reddit_mentions` | `ticker`, `mentions`, `date`, `_retrieved` |
| `analyst_ratings` | `ticker`, `rating`, `date`, `_retrieved` |
| `news_headlines` | `ticker`, `headline`, `link`, `source`, `time`, `_retrieved` |
| `insider_buying` | `ticker`, `exec`, `shares`, `date`, `_retrieved` |
| `sp500_index` | `date`, `open`, `high`, `low`, `close`, `volume`, `_retrieved` |
| `volatility_momentum` | `symbol`, `date`, `_retrieved` |
| `leveraged_sector_momentum` | `symbol`, `date`, `_retrieved` |
| `sector_momentum_weekly` | `symbol`, `date`, `_retrieved` |
| `smallcap_momentum_weekly` | `symbol`, `date`, `_retrieved` |
| `upgrade_momentum_weekly` | `symbol`, `date`, `_retrieved` |
| `returns` | `date`, `strategy`, `return_pct` |
| `risk_stats` | `date`, `strategy`, `var95`, `var99`, `es95`, `es99`, `vol30d`, `beta30d`, `max_drawdown` |
| `risk_rules` | `id`, `name`, `strategy`, `metric`, `operator`, `threshold`, `created_at` |
| `risk_alerts` | `id`, `rule_id`, `strategy`, `metric_value`, `triggered_at`, `is_acknowledged` |
| `ticker_scores` | `symbol`, `index_name`, `date`, `fundamentals`, `momentum`, `liquidity_sentiment`, `risk_adjusted`, `overall` |
| `top_scores` | `date`, `symbol`, `index_name`, `score`, `rank` |
| `portfolios` | `id`, `name`, `weights` |
| `trades` | `portfolio_id`, `symbol`, `qty`, `side`, `price`, `timestamp`, `cost_basis`, `realized_pnl` |
| `weight_history` | `portfolio_id`, `date`, `weights` |
| `metrics` | `portfolio_id`, `date`, `ret`, `ret_1d`, `ret_7d`, `ret_30d`, `ret_3m`, `ret_6m`, `ret_1y`, `ret_2y`, `sharpe`, `sortino`, `weekly_vol`, `weekly_sortino`, `alpha`, `beta`, `beta_smb`, `beta_hml`, `ff_expected_return`, `max_drawdown`, `cagr`, `win_rate`, `annual_vol`, `information_ratio`, `treynor_ratio`, `var`, `cvar`, `exposure`, `atr_14d`, `rsi_14d` |
| `account_metrics_paper` | `id`, `timestamp`, `equity`, `last_equity` |
| `account_metrics_live` | `id`, `timestamp`, `equity`, `last_equity` |
| `system_logs` | `timestamp`, `level`, `logger`, `message` |
| `positions` | `portfolio_id`, `symbol`, `qty`, `cost_basis`, `realized_pnl` |
| `universe` | `symbol`, `index_name`, `_retrieved` |

All tables are exposed through the API. Use `/db` to list available tables and `/db/{table}` to retrieve rows in JSON or CSV for tabular display on the front end.

Every column is stored as a string except for the timestamp `_retrieved` which is a `TIMESTAMP` in UTC.

Both the `metrics` table and the `account_metrics_paper`/`account_metrics_live` tables are populated nightly by
the scheduler so that portfolio performance and account equity remain up
to date.

The `metrics` table captures daily exposure alongside risk statistics such
as Value at Risk (`var`), Conditional VaR (`cvar`) and `max_drawdown` for
each portfolio.

## Caching

Metrics queries are wrapped in a lightweight in-memory cache. Results are
cached for ``CACHE_TTL`` seconds (900 by default) to minimise database
load when charts poll for updates.

Ticker constituents from the S&P 500, S&P 400 and Russell 2000 are
combined in the `universe` table with an `index_name` label. The
`scrapers/universe.py` helper downloads each list and writes CSV copies
under `cache/universes/` for offline use.
Composite scores in `ticker_scores` are calculated by ranking each metric
across the entire universe and applying the weights listed in the README.
The `top_scores` table archives the highest ranked names after each monthly update.
Fundamental ratios like the Piotroski F‑Score, Altman Z‑Score, ROIC and
Free Cash Flow Yield are computed entirely from Yahoo Finance statements.
`weight_history` simply records the raw weight vector for each portfolio.
