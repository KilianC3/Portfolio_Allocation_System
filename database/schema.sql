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

CREATE TABLE IF NOT EXISTS sp500_index (
    id SERIAL PRIMARY KEY,
    date TEXT UNIQUE,
    close DOUBLE PRECISION,
    _retrieved TIMESTAMPTZ
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
    data JSONB
);
