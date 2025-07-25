# Portfolio Allocation System

The Portfolio Allocation System is an end-to-end trading platform that runs entirely on a single server.  It gathers alternative data, builds equity portfolios and sends orders to Alpaca.  A FastAPI service exposes metrics and trading endpoints while scheduled jobs update data automatically.

## Setup

1. **Install the application**

   ```bash
   git clone <repo_url>
   cd Portfolio_Allocation_System
   python3 -m venv venv
   source venv/bin/activate
   pip install -r deploy/requirements.txt
   ```

2. **Configure the service**

   Edit `service/config.yaml` and set these values:

   - `API_HOST: "192.168.0.59"`
   - `PG_URI`: MariaDB URI pointing to `192.168.0.59`
   - `ALPACA_PAPER_KEY`, `ALPACA_PAPER_SECRET`
   - `ALPACA_PAPER_URL: "https://paper-api.alpaca.markets"`
   - `ALPACA_LIVE_URL: "https://api.alpaca.markets"`
  - `API_TOKEN`: token for authenticating requests
  - `REDIS_URL`: `redis://:<API_TOKEN>@192.168.0.59:6379/0`

   The service appends `/v2/account` to the Alpaca URLs automatically, so do **not** include the `/v2` prefix in the configuration.

3. **Setup Redis**

   ```bash
   sudo scripts/setup_redis.sh
   ```
   (This step is also run automatically by `bootstrap.sh`.)
   The script binds Redis to `192.168.0.59` and sets
   `requirepass` in `/etc/redis/redis.conf` to the same
   `API_TOKEN` value used by the application.

4. **Enable remote MariaDB access**

   The `scripts/bootstrap.sh` script configures MariaDB to listen on all
   interfaces by setting `bind-address = 192.168.0.59` in
   `/etc/mysql/mariadb.conf.d/50-server.cnf` and opens port `3306` on the
   firewall.  Grant the database user remote privileges so the API and scrapers
   can connect:

   ```bash
   sudo mysql -e "GRANT ALL PRIVILEGES ON quant_fund.* TO 'maria'@'%' IDENTIFIED BY 'maria'; FLUSH PRIVILEGES;"
   mysql -e 'SELECT User, Host FROM mysql.user;'
   ```

   Ensure that the output lists `maria` with host `%` to confirm remote access
   is enabled.

5. **Start all services**

   ```bash
   sudo scripts/bootstrap.sh
   ```

   This registers a systemd unit that runs `service/start.py` and launches the API at `http://192.168.0.59:8001`.

6. **Run the unit tests** *(optional)*

   ```bash
   pip install -r deploy/requirements-test.txt
   pytest -q
   ```

## Usage

Send authenticated requests using either the `Authorization` header or a `token` query parameter:

```bash
curl "http://192.168.0.59:8001/db/trades?limit=20&token=<YOUR_TOKEN>"
```

Convenience scripts:

- `scripts/dashboard.py` – print table samples directly in the terminal
- `scripts/populate.py` – refresh datasets without starting the API
- `scripts/expose_db_api.sh` – expose the API on a different host and port

### Dashboard

After the API is running you can explore data in your browser:

```
http://192.168.0.59:8001/dashboard?token=<YOUR_TOKEN>
```

This page lists scheduled jobs and links to every database table. The dashboard
opens automatically when `service.start` launches. The same information is
available from the command line:

```bash
source venv/bin/activate
python scripts/dashboard.py
```

Access the structured log records directly via:

```
http://192.168.0.59:8001/dashboard?table=system_logs&token=<YOUR_TOKEN>
```

## Troubleshooting

- **Alpaca 404** – verify that `ALPACA_PAPER_URL` and `ALPACA_LIVE_URL` are just the domain.  The service calls `/v2/account` itself, so a trailing `/v2` would lead to `/v2/v2/account` and a 404.
- **Redis connection refused** – ensure a Redis instance is running on `192.168.0.59:6379` or update the ledger configuration.
- Watch logs with `journalctl -u portfolio -f` if startup checks fail.

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
- `sp500_index` – weekly OHLCV history for the S&P 500
- `universe` – full list of tradable symbols with `index_name`
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

Run `database.init_db()` whenever the schema changes to ensure the `cache` table uses `MEDIUMTEXT`.

Further documentation is located in the `docs/` directory.

