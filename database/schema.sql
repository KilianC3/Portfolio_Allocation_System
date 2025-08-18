CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS portfolios (
    id VARCHAR(36) PRIMARY KEY,
    name TEXT,
    weights JSON
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    portfolio_id VARCHAR(36) REFERENCES portfolios(id),
    symbol VARCHAR(16),
    qty DOUBLE,
    side TEXT,
    price DOUBLE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS weight_history (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    portfolio_id VARCHAR(36) REFERENCES portfolios(id),
    date DATE,
    weights JSON,
    UNIQUE(portfolio_id, date)
);


CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    portfolio_id VARCHAR(36) REFERENCES portfolios(id),
    date DATE,
    ret DOUBLE,
    benchmark DOUBLE,
    sharpe DOUBLE,
    alpha DOUBLE,
    beta DOUBLE,
    beta_smb DOUBLE,
    beta_hml DOUBLE,
    ff_expected_return DOUBLE,
    max_drawdown DOUBLE,
    ret_1d DOUBLE,
    ret_7d DOUBLE,
    ret_30d DOUBLE,
    ret_3m DOUBLE,
    ret_6m DOUBLE,
    ret_1y DOUBLE,
    ret_2y DOUBLE,
    cagr DOUBLE,
    win_rate DOUBLE,
    avg_win DOUBLE,
    avg_loss DOUBLE,
    annual_vol DOUBLE,
    annual_std DOUBLE,
    information_ratio DOUBLE,
    treynor_ratio DOUBLE,
    total_trades INTEGER,
    var DOUBLE,
    cvar DOUBLE,
    UNIQUE(portfolio_id, date)
);
CREATE TABLE IF NOT EXISTS allocation_performance (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date DATE,
    method TEXT,
    ret DOUBLE,
    UNIQUE(date, method)
);
CREATE TABLE IF NOT EXISTS politician_trades (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    politician TEXT,
    ticker TEXT,
    transaction TEXT,
    amount TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(politician, ticker, date)
);

CREATE TABLE IF NOT EXISTS lobbying (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    client TEXT,
    amount TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS wiki_views (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    views BIGINT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS dc_insider_scores (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    score TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS gov_contracts (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    value TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS app_reviews (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    hype TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS google_trends (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    score TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS analyst_ratings (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date_utc DATETIME,
    ticker TEXT,
    company TEXT,
    analyst TEXT,
    rating_current TEXT,
    pt_prior DOUBLE,
    pt_current DOUBLE,
    pt_pct_change DOUBLE,
    importance TEXT,
    notes TEXT,
    action TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date_utc)
);

CREATE TABLE IF NOT EXISTS news_headlines (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    headline TEXT,
    link TEXT,
    source TEXT,
    time TEXT,
    sentiment FLOAT,
    _retrieved TIMESTAMP
);

CREATE TABLE IF NOT EXISTS insider_buying (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    exec TEXT,
    shares TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, exec, date)
);

CREATE TABLE IF NOT EXISTS reddit_mentions (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    mentions INTEGER,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS sp500_index (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date TEXT UNIQUE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    _retrieved TIMESTAMP
);

CREATE TABLE IF NOT EXISTS universe (
    symbol VARCHAR(16) PRIMARY KEY,
    index_name TEXT,
    _retrieved TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticker_scores (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    index_name TEXT,
    date DATE,
    fundamentals DOUBLE,
    momentum DOUBLE,
    liquidity_sentiment DOUBLE,
    risk_adjusted DOUBLE,
    overall DOUBLE,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS top_scores (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date DATE,
    symbol VARCHAR(16),
    index_name TEXT,
    score DOUBLE,
    rank INTEGER,
    UNIQUE(date, symbol)
);


CREATE TABLE IF NOT EXISTS alloc_log (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    data JSON
);

CREATE TABLE IF NOT EXISTS cache (
    cache_key VARCHAR(191) PRIMARY KEY,
    payload MEDIUMTEXT,
    expire TIMESTAMP
);
ALTER TABLE cache MODIFY payload MEDIUMTEXT;

CREATE TABLE IF NOT EXISTS account_metrics (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    equity DOUBLE,
    last_equity DOUBLE
);

CREATE TABLE IF NOT EXISTS account_metrics_paper (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    equity DOUBLE,
    last_equity DOUBLE
);

CREATE TABLE IF NOT EXISTS account_metrics_live (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    equity DOUBLE,
    last_equity DOUBLE
);

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    level TEXT,
    logger TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS volatility_momentum (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    score DOUBLE,
    ret_52w DOUBLE,
    vol_12w DOUBLE,
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS leveraged_sector_momentum (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    ret DOUBLE,
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS sector_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    ret DOUBLE,
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS smallcap_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    price DOUBLE,
    ret DOUBLE,
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS upgrade_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    ratio DOUBLE,
    upgrades INTEGER,
    downgrades INTEGER,
    total INTEGER,
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS returns (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date DATE,
    strategy VARCHAR(64),
    return_pct DOUBLE,
    UNIQUE(date, strategy)
);

CREATE TABLE IF NOT EXISTS risk_stats (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    date DATE,
    strategy VARCHAR(64),
    var95 DOUBLE,
    var99 DOUBLE,
    es95 DOUBLE,
    es99 DOUBLE,
    vol30d DOUBLE,
    beta30d DOUBLE,
    max_drawdown DOUBLE,
    UNIQUE(date, strategy)
);

CREATE TABLE IF NOT EXISTS risk_rules (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    name TEXT,
    strategy VARCHAR(64),
    metric VARCHAR(32),
    operator VARCHAR(4),
    threshold DOUBLE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_alerts (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    rule_id INTEGER REFERENCES risk_rules(id),
    strategy VARCHAR(64),
    metric_value DOUBLE,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_acknowledged BOOLEAN DEFAULT FALSE
);

-- Track scheduler job runtimes
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) PRIMARY KEY,
    last_run DATETIME NULL,
    next_run DATETIME NULL
);

-- Ensure composite unique keys for daily snapshots
ALTER TABLE wiki_views DROP INDEX IF EXISTS ticker;
ALTER TABLE wiki_views ADD UNIQUE KEY IF NOT EXISTS uq_wiki_views_ticker_date (ticker, date);
ALTER TABLE wiki_views DROP COLUMN IF EXISTS page;
ALTER TABLE wiki_views MODIFY COLUMN views BIGINT;

ALTER TABLE google_trends DROP INDEX IF EXISTS ticker;
ALTER TABLE google_trends ADD UNIQUE KEY IF NOT EXISTS uq_google_trends (ticker, date);

ALTER TABLE reddit_mentions DROP INDEX IF EXISTS ticker;
ALTER TABLE reddit_mentions ADD UNIQUE KEY IF NOT EXISTS uq_reddit_mentions (ticker, date);

ALTER TABLE app_reviews DROP INDEX IF EXISTS ticker;
ALTER TABLE app_reviews ADD UNIQUE KEY IF NOT EXISTS uq_app_reviews (ticker, date);

ALTER TABLE gov_contracts DROP INDEX IF EXISTS ticker;
ALTER TABLE gov_contracts ADD UNIQUE KEY IF NOT EXISTS uq_gov_contracts (ticker, date, value);

ALTER TABLE volatility_momentum DROP INDEX IF EXISTS symbol;
ALTER TABLE volatility_momentum ADD UNIQUE KEY IF NOT EXISTS uq_volmom (symbol, date);

ALTER TABLE leveraged_sector_momentum DROP INDEX IF EXISTS symbol;
ALTER TABLE leveraged_sector_momentum ADD UNIQUE KEY IF NOT EXISTS uq_levmom (symbol, date);

ALTER TABLE sector_momentum_weekly DROP INDEX IF EXISTS symbol;
ALTER TABLE sector_momentum_weekly ADD UNIQUE KEY IF NOT EXISTS uq_secmom (symbol, date);

ALTER TABLE smallcap_momentum_weekly DROP INDEX IF EXISTS symbol;
ALTER TABLE smallcap_momentum_weekly ADD UNIQUE KEY IF NOT EXISTS uq_smallmom (symbol, date);

ALTER TABLE upgrade_momentum_weekly DROP INDEX IF EXISTS symbol;
ALTER TABLE upgrade_momentum_weekly ADD UNIQUE KEY IF NOT EXISTS uq_upgdmom (symbol, date);

ALTER TABLE analyst_ratings DROP INDEX IF EXISTS ticker;
ALTER TABLE news_headlines ADD COLUMN IF NOT EXISTS sentiment FLOAT;
ALTER TABLE analyst_ratings
  ADD COLUMN IF NOT EXISTS date_utc DATETIME,
  ADD COLUMN IF NOT EXISTS company TEXT,
  ADD COLUMN IF NOT EXISTS analyst TEXT,
  ADD COLUMN IF NOT EXISTS rating_current TEXT,
  ADD COLUMN IF NOT EXISTS pt_prior DOUBLE,
  ADD COLUMN IF NOT EXISTS pt_current DOUBLE,
  ADD COLUMN IF NOT EXISTS pt_pct_change DOUBLE,
  ADD COLUMN IF NOT EXISTS importance TEXT,
  ADD COLUMN IF NOT EXISTS notes TEXT,
  ADD COLUMN IF NOT EXISTS action TEXT,
  ADD UNIQUE KEY IF NOT EXISTS uq_analyst_ratings (ticker, date_utc);

ALTER TABLE ticker_scores ADD INDEX IF NOT EXISTS idx_ticker_scores_index_name (index_name);
ALTER TABLE metrics ADD INDEX IF NOT EXISTS idx_metrics_portfolio (portfolio_id);
