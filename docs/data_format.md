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

Every column is stored as a string except for the timestamp `_retrieved` which is a `TIMESTAMP` in UTC.
