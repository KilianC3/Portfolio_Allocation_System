"""Async Postgres database helpers using SQLAlchemy."""

from __future__ import annotations

import os
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Float,
    DateTime,
    Date,
    Integer,
    JSON,
    text,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from logger import get_logger
from config import DATABASE_URL

_log = get_logger("db")

metadata = MetaData()

portfolios = Table(
    "portfolios",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("weights", JSON),
)

trades = Table(
    "trades",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("portfolio_id", String, nullable=False, index=True),
    Column("timestamp", DateTime, index=True),
    Column("symbol", String),
    Column("side", String),
    Column("qty", Float),
    Column("price", Float),
)

metrics = Table(
    "metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("portfolio_id", String, nullable=False, index=True),
    Column("date", Date, nullable=False, index=True),
    Column("ret", Float),
    Column("benchmark", Float),
    Column("sharpe", Float),
    Column("alpha", Float),
    Column("beta", Float),
    Column("max_drawdown", Float),
)

cache = Table(
    "cache",
    metadata,
    Column("key", String, primary_key=True),
    Column("payload", String),
    Column("expire", DateTime, index=True),
)

account_metrics = Table(
    "account_metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", DateTime, index=True),
    Column("paper", String),
    Column("equity", Float),
    Column("last_equity", Float),
)

politician_trades = Table(
    "politician_trades",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("politician", String),
    Column("ticker", String),
    Column("transaction", String),
    Column("amount", String),
    Column("date", String),
    Column("_retrieved", DateTime),
)

lobbying = Table(
    "lobbying",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String),
    Column("client", String),
    Column("amount", String),
    Column("date", String),
    Column("_retrieved", DateTime),
)

wiki_views = Table(
    "wiki_views",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String),
    Column("views", String),
    Column("date", String),
    Column("_retrieved", DateTime),
)

dc_insider_scores = Table(
    "dc_insider_scores",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String),
    Column("score", String),
    Column("date", String),
    Column("_retrieved", DateTime),
)

gov_contracts = Table(
    "gov_contracts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String),
    Column("value", String),
    Column("date", String),
    Column("_retrieved", DateTime),
)

# Backwards compatibility aliases
pf_coll = portfolios
trade_coll = trades
metric_coll = metrics
lobby_coll = lobbying
politician_coll = politician_trades
wiki_collection = wiki_views
insider_coll = dc_insider_scores
contracts_coll = gov_contracts
account_coll = account_metrics

async_engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)


async def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_trades_pf_ts ON trades (portfolio_id, timestamp)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_metrics_pf_date ON metrics (portfolio_id, date)"
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_cache_expire ON cache (expire)")
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_account_ts ON account_metrics (timestamp)"
            )
        )


__all__ = [
    "async_engine",
    "AsyncSessionLocal",
    "init_db",
    "portfolios",
    "trades",
    "metrics",
    "cache",
    "account_metrics",
    "pf_coll",
    "trade_coll",
    "metric_coll",
    "lobby_coll",
    "politician_coll",
    "wiki_collection",
    "insider_coll",
    "contracts_coll",
    "account_coll",
]
