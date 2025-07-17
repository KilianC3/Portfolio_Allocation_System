CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS portfolios (
    id TEXT PRIMARY KEY,
    name TEXT,
    weights JSONB
);

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    portfolio_id TEXT REFERENCES portfolios(id),
    symbol TEXT,
    qty DOUBLE PRECISION,
    side TEXT,
    price DOUBLE PRECISION,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS weight_history (
    id SERIAL PRIMARY KEY,
    portfolio_id TEXT REFERENCES portfolios(id),
    date DATE,
    weights JSONB,
    UNIQUE(portfolio_id, date)
);


CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    portfolio_id TEXT REFERENCES portfolios(id),
    date DATE,
    ret DOUBLE PRECISION,
    benchmark DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    alpha DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    ret_1d DOUBLE PRECISION,
    ret_7d DOUBLE PRECISION,
    ret_30d DOUBLE PRECISION,
    ret_3m DOUBLE PRECISION,
    ret_6m DOUBLE PRECISION,
    ret_1y DOUBLE PRECISION,
    ret_2y DOUBLE PRECISION,
    cagr DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    avg_win DOUBLE PRECISION,
    avg_loss DOUBLE PRECISION,
    annual_vol DOUBLE PRECISION,
    annual_std DOUBLE PRECISION,
    information_ratio DOUBLE PRECISION,
    treynor_ratio DOUBLE PRECISION,
    total_trades INTEGER,
    var DOUBLE PRECISION,
    cvar DOUBLE PRECISION,
    UNIQUE(portfolio_id, date)
);
CREATE TABLE IF NOT EXISTS politician_trades (
    id SERIAL PRIMARY KEY,
    politician TEXT,
    ticker TEXT,
    transaction TEXT,
    amount TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(politician, ticker, date)
);

CREATE TABLE IF NOT EXISTS lobbying (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    client TEXT,
    amount TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS wiki_views (
    id SERIAL PRIMARY KEY,
    page TEXT,
    views TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(page, date)
);

CREATE TABLE IF NOT EXISTS dc_insider_scores (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    score TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS gov_contracts (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    value TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS app_reviews (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    hype TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS google_trends (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    score TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS analyst_ratings (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    rating TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, rating, date)
);

CREATE TABLE IF NOT EXISTS news_headlines (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    headline TEXT,
    link TEXT,
    source TEXT,
    time TEXT,
    _retrieved TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS insider_buying (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    exec TEXT,
    shares TEXT,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, exec, date)
);

CREATE TABLE IF NOT EXISTS reddit_mentions (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    mentions INTEGER,
    pos INTEGER,
    neu INTEGER,
    neg INTEGER,
    date TEXT,
    _retrieved TIMESTAMPTZ,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS sp500_index (
    id SERIAL PRIMARY KEY,
    date TEXT UNIQUE,
    close DOUBLE PRECISION,
    _retrieved TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    index_name TEXT,
    _retrieved TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ticker_scores (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    index_name TEXT,
    date DATE,
    fundamentals DOUBLE PRECISION,
    momentum DOUBLE PRECISION,
    liquidity_sentiment DOUBLE PRECISION,
    risk_adjusted DOUBLE PRECISION,
    overall DOUBLE PRECISION,
    UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS top_scores (
    id SERIAL PRIMARY KEY,
    date DATE,
    symbol TEXT,
    index_name TEXT,
    score DOUBLE PRECISION,
    rank INTEGER,
    UNIQUE(date, symbol)
);


CREATE TABLE IF NOT EXISTS alloc_log (
    id SERIAL PRIMARY KEY,
    data JSONB
);

CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    payload TEXT,
    expire TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS account_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    equity DOUBLE PRECISION,
    last_equity DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS account_metrics_paper (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    equity DOUBLE PRECISION,
    last_equity DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS account_metrics_live (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    equity DOUBLE PRECISION,
    last_equity DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    level TEXT,
    logger TEXT,
    message TEXT
);
