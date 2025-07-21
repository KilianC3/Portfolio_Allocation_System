# Data Store Format

Scrapers normalise the raw HTML tables from QuiverQuant into columnar snapshots stored in DuckDB.
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
| `reddit_mentions` | `ticker`, `mentions`, `pos`, `neu`, `neg`, `date`, `_retrieved` |
| `analyst_ratings` | `ticker`, `rating`, `date`, `_retrieved` |
| `news_headlines` | `ticker`, `headline`, `link`, `source`, `time`, `_retrieved` |
| `insider_buying` | `ticker`, `exec`, `shares`, `date`, `_retrieved` |
| `sp500_index` | `date`, `close`, `_retrieved` |
| `ticker_scores` | `symbol`, `index_name`, `date`, `fundamentals`, `momentum`, `liquidity_sentiment`, `risk_adjusted`, `overall` |
| `top_scores` | `date`, `symbol`, `index_name`, `score`, `rank` |
| `portfolios` | `id`, `name`, `weights` |
| `trades` | `portfolio_id`, `symbol`, `qty`, `side`, `price`, `timestamp` |
| `weight_history` | `portfolio_id`, `date`, `weights` |
| `metrics` | `portfolio_id`, `date`, `ret_1d`, `ret_7d`, `ret_30d`, `ret_3m`, `ret_6m`, `ret_1y`, `ret_2y`, `sharpe`, `sortino`, `weekly_vol`, `weekly_sortino`, `alpha`, `beta`, `max_drawdown`, `cagr`, `win_rate`, `information_ratio`, `treynor_ratio`, `var`, `cvar`, `atr_14d`, `rsi_14d` |
| `account_metrics_paper` | `id`, `timestamp`, `equity`, `last_equity` |
| `account_metrics_live` | `id`, `timestamp`, `equity`, `last_equity` |
| `universe` | `symbol`, `index_name`, `_retrieved` |

Every column is stored as a string except for the timestamp `_retrieved` which is a `TIMESTAMP` in UTC.

Both the `metrics` table and the `account_metrics_paper`/`account_metrics_live` tables are populated nightly by
the scheduler so that portfolio performance and account equity remain up
to date.

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
