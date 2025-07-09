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
| `analyst_ratings` | `ticker`, `rating`, `date`, `_retrieved` |
| `news_headlines` | `ticker`, `headline`, `link`, `source`, `time`, `_retrieved` |
| `insider_buying` | `ticker`, `exec`, `shares`, `date`, `_retrieved` |
| `sp500_index` | `date`, `close`, `_retrieved` |
| `portfolios` | `id`, `name`, `weights` |
| `trades` | `portfolio_id`, `symbol`, `qty`, `side`, `price`, `timestamp` |
| `metrics` | `portfolio_id`, `date`, `ret`, `ret_7d`, `ret_30d`, `ret_1y`, `benchmark`, `sharpe`, `alpha`, `beta`, `max_drawdown` |
| `account_metrics` | `timestamp`, `data` |
| `universe` | `index`, `symbol`, `_retrieved` |

Every column is stored as a string except for the timestamp `_retrieved` which is a `TIMESTAMP` in UTC.

Both the `metrics` and `account_metrics` tables are populated nightly by
the scheduler so that portfolio performance and account equity remain up
to date.

The `universe` table stores ticker constituents for the S&P 500,
S&P 1500 and Russell 2000 indexes. The `scrapers/universe.py` helper
persists the lists to this table and also writes a CSV copy under
`cache/universes/` for offline use.
