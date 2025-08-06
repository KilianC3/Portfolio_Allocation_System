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
    page TEXT,
    views TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(page, date)
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
    ticker TEXT,
    rating TEXT,
    date TEXT,
    _retrieved TIMESTAMP,
    UNIQUE(ticker, rating, date)
);

CREATE TABLE IF NOT EXISTS news_headlines (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker TEXT,
    headline TEXT,
    link TEXT,
    source TEXT,
    time TEXT,
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
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS leveraged_sector_momentum (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS sector_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS smallcap_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
    date DATE,
    _retrieved TIMESTAMP,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS upgrade_momentum_weekly (
    id INTEGER AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(16),
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
