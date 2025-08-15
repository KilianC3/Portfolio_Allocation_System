"""Database helpers for MariaDB access."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import json
import pymysql
from pymysql.cursors import DictCursor
from pymysql.connections import Connection
from urllib.parse import urlparse
import datetime as dt
from queue import Queue, Empty, Full

from service.logger import get_logger, register_db_handler
from service.config import DB_URI, ALLOW_LIVE

_log = get_logger("db")

PLACEHOLDER = "%s"

_pool: Optional["_ConnectionPool"] = None


class _ConnectionPool:
    """Simple PyMySQL connection pool."""

    def __init__(self, kwargs: Dict[str, Any], maxsize: int = 5) -> None:
        self.kwargs = kwargs
        self._q: Queue[Connection] = Queue(maxsize)

    def get(self) -> Connection:
        try:
            conn = self._q.get_nowait()
        except Empty:
            conn = pymysql.connect(**self.kwargs)
        return conn

    def put(self, conn: Connection) -> None:
        try:
            if conn.open:
                self._q.put_nowait(conn)
            else:
                conn.close()
        except Full:
            conn.close()


class _PoolConnProxy:
    """Proxy object returning cursors from the pool."""

    def __init__(self, pool: _ConnectionPool):
        self.pool = pool

    class _CursorCtx:
        def __init__(self, conn: Connection, pool: _ConnectionPool):
            self.conn = conn
            self.pool = pool

        def __enter__(self):
            self.cur = self.conn.cursor()
            return self.cur

        def __exit__(self, exc_type, exc, tb):
            self.cur.close()
            self.pool.put(self.conn)

    def cursor(self):  # pragma: no cover - thin wrapper
        conn = self.pool.get()
        return self._CursorCtx(conn, self.pool)


try:
    parts = urlparse(DB_URI)
    _conn_args: Dict[str, Any] = dict(
        host=parts.hostname or "192.168.0.59",
        user=parts.username or "root",
        password=parts.password or "",
        database=parts.path.lstrip("/"),
        port=parts.port or 8001,
        autocommit=True,
        cursorclass=DictCursor,
    )
    _pool = _ConnectionPool(_conn_args)
    conn = _pool.get()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
    _pool.put(conn)
except Exception as e:  # pragma: no cover - db may not exist in tests
    _log.error(f"MariaDB connection failed: {e}")
    _pool = None


def _ensure_conn() -> bool:
    """Ping the connection and reconnect if needed."""
    if not _pool:
        return False
    conn = _pool.get()
    try:
        conn.ping(reconnect=True)
        return True
    except Exception as exc:
        _log.error("MariaDB reconnect failed: %s", exc)
        try:
            conn.close()
        finally:
            return False
    finally:
        if _pool:
            _pool.put(conn)


def db_ping() -> bool:
    """Return True if the MariaDB connection is healthy."""
    if not _ensure_conn():
        return False
    if not _pool:
        return False
    conn = _pool.get()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:  # pragma: no cover - transient errors
        _log.error(f"Database ping failed: {exc}")
        return False
    finally:
        _pool.put(conn)


class InMemoryCollection:
    """Minimal in-memory fallback used when MariaDB is unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def find_one(self, q: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cache_key = q.get("cache_key")
        if not isinstance(cache_key, str):
            return None
        return self._store.get(cache_key)

    def replace_one(
        self, match: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ) -> None:
        self._store[match["cache_key"]] = doc


class PGClient:
    def __init__(self, pool):
        self._pool = pool

    @property
    def admin(self) -> "PGClient":
        return self

    def command(self, cmd: str) -> None:
        if cmd == "ping" and self._pool:
            db_ping()


class PGDatabase:
    def __init__(self, pool):
        self.pool = pool
        self.client = PGClient(pool)

    @property
    def conn(self):  # pragma: no cover - for legacy access
        return _PoolConnProxy(self.pool) if self.pool else None

    def __getitem__(self, name: str) -> "PGCollection":
        return PGCollection(self.pool, name, self)


def _build_where(q: Dict[str, Any]) -> Tuple[str, List[Any]]:
    if not q:
        return "", []
    clauses: List[str] = []
    params: List[Any] = []
    for k, v in q.items():
        col = "id" if k == "_id" else k
        if isinstance(v, dict):
            sub = []
            if "$gte" in v:
                sub.append(f"{col}>={PLACEHOLDER}")
                params.append(v["$gte"])
            if "$lte" in v:
                sub.append(f"{col}<={PLACEHOLDER}")
                params.append(v["$lte"])
            clauses.append(" AND ".join(sub))
        else:
            clauses.append(f"{col}={PLACEHOLDER}")
            params.append(v)
    return " AND ".join(clauses), params


class PGQuery:
    def __init__(
        self, pool, table: str, where: str = "", params: Iterable[Any] | None = None
    ):
        self.pool = pool
        self.table = table
        self.where = where
        self.params = list(params or [])
        self.order = ""
        self.limit_n: Optional[int] = None
        self.offset_n: Optional[int] = None

    def sort(self, field: str, direction: int) -> "PGQuery":
        col = "id" if field == "_id" else field
        self.order = f" ORDER BY {col} {'DESC' if direction < 0 else 'ASC'}"
        return self

    def limit(self, n: int) -> "PGQuery":
        self.limit_n = n
        return self

    def offset(self, n: int) -> "PGQuery":
        self.offset_n = n
        return self

    def _sql(self) -> Tuple[str, List[Any]]:
        sql = f"SELECT * FROM {self.table}"
        params = list(self.params)
        if self.where:
            sql += " WHERE " + self.where
        if self.order:
            sql += self.order
        if self.limit_n is not None:
            sql += f" LIMIT {self.limit_n}"
        if self.offset_n is not None:
            sql += f" OFFSET {self.offset_n}"
        return sql, params

    def __iter__(self):
        if not self.pool:
            return iter([])
        db_ping()
        sql, params = self._sql()
        conn = self.pool.get()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            self.pool.put(conn)
        for r in rows:
            if "id" in r:
                r["_id"] = r.pop("id")
        return iter(rows)

    def __next__(self):  # pragma: no cover - not used directly
        return next(iter(self))


class PGCollection:
    def __init__(self, pool, table: str, database: PGDatabase | None = None):
        self.pool = pool
        self.table = table
        self._database = database or PGDatabase(pool)

    @property
    def conn(self):  # pragma: no cover - for legacy access
        return _PoolConnProxy(self.pool) if self.pool else None

    @property
    def database(self) -> PGDatabase:
        return self._database

    # no-op for index creation
    def create_index(self, *args, **kwargs) -> None:
        return None

    def find_one(
        self, q: Dict[str, Any] | None = None, sort: List[Tuple[str, int]] | None = None
    ):
        qry = self.find(q)
        if sort:
            field, direction = sort[0]
            qry.sort(field, direction)
        qry.limit(1)
        rows = list(qry)
        return rows[0] if rows else None

    def find(
        self, q: Dict[str, Any] | None = None, projection: Dict[str, int] | None = None
    ) -> PGQuery:
        where, params = _build_where(q or {})
        return PGQuery(self.pool, self.table, where, params)

    def delete_many(self, q: Dict[str, Any]):
        if not self.pool:
            return
        db_ping()
        where, params = _build_where(q)
        sql = f"DELETE FROM {self.table}"
        if where:
            sql += " WHERE " + where
        conn = self.pool.get()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        finally:
            self.pool.put(conn)

    def insert_many(self, docs: List[Dict[str, Any]]):
        if not self.pool or not docs:
            return
        db_ping()
        cols = ["id" if c == "_id" else c for c in docs[0].keys()]
        values = [
            [json.dumps(d[c]) if isinstance(d[c], (dict, list)) else d[c] for c in d]
            for d in docs
        ]
        placeholders = ",".join(
            ["(" + ",".join([PLACEHOLDER] * len(cols)) + ")" for _ in values]
        )
        flat = [v for row in values for v in row]
        updates = ",".join([f"{c}=VALUES({c})" for c in cols])
        sql = (
            f"INSERT INTO {self.table} ({','.join(cols)}) VALUES {placeholders} "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
        conn = self.pool.get()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, flat)
        finally:
            self.pool.put(conn)

    def insert_one(self, doc: Dict[str, Any]):
        self.insert_many([doc])

    def update_one(
        self, match: Dict[str, Any], update: Dict[str, Any], upsert: bool = False
    ):
        if not self.pool:
            return
        db_ping()
        item = update.get("$set", {}).copy()
        item.update(match)
        cols = ["id" if c == "_id" else c for c in item.keys()]
        vals = [
            json.dumps(item[k]) if isinstance(item[k], (dict, list)) else item[k]
            for k in item
        ]
        placeholders = ",".join([PLACEHOLDER] * len(cols))
        conn = self.pool.get()
        try:
            if upsert:
                updates = ",".join([f"{c}=VALUES({c})" for c in cols])
                sql = (
                    f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {updates}"
                )
                with conn.cursor() as cur:
                    cur.execute(sql, vals)
            else:
                set_clause = ",".join([f"{c}={PLACEHOLDER}" for c in cols])
                where, params = _build_where(match)
                sql = f"UPDATE {self.table} SET {set_clause} WHERE {where}"
                with conn.cursor() as cur:
                    cur.execute(sql, vals + params)
        finally:
            self.pool.put(conn)

    # alias used by smart_scraper
    def replace_one(
        self, match: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ):
        self.update_one(match, {"$set": doc}, upsert=upsert)

    def count_documents(self, q: Dict[str, Any]) -> int:
        """Return the number of documents matching ``q``."""
        if not self.pool:
            return 0
        db_ping()
        where, params = _build_where(q)
        sql = f"SELECT COUNT(*) AS cnt FROM {self.table}"
        if where:
            sql += " WHERE " + where
        conn = self.pool.get()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        finally:
            self.pool.put(conn)
        if not row:
            return 0
        return int(next(iter(row.values())))


def init_db() -> None:
    """Initialise tables from ``schema.sql`` and record schema version."""
    if not _pool:
        return

    def exec_sql(sql: str) -> None:
        conn = _pool.get()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
        finally:
            _pool.put(conn)

    schema_path = Path(__file__).with_name("schema.sql")
    with open(schema_path) as f:
        sql = f.read()

    for statement in sql.split(";"):
        stmt = statement.strip()
        if not stmt:
            continue
        exec_sql(stmt)

    # record version 1 if not present
    exec_sql("INSERT IGNORE INTO schema_version (version) VALUES (1)")


db = PGDatabase(_pool)

pf_coll = db["portfolios"]
trade_coll = db["trades"]
position_coll = db["positions"]
position_coll.create_index([("portfolio_id", 1), ("symbol", 1)], unique=True)
metric_coll = db["metrics"]
politician_coll = db["politician_trades"]
weight_coll = db["weight_history"]
lobbying_coll = db["lobbying"]
lobby_coll = lobbying_coll
wiki_coll = db["wiki_views"]
insider_coll = db["dc_insider_scores"]
contracts_coll = db["gov_contracts"]
alloc_log_coll = db["alloc_log"]
alloc_perf_coll = db["allocation_performance"]
cache = db["cache"] if _pool else InMemoryCollection()
account_paper_coll = db["account_metrics_paper"]
account_live_coll = db["account_metrics_live"]
account_coll = account_live_coll if ALLOW_LIVE else account_paper_coll
app_reviews_coll = db["app_reviews"]
google_trends_coll = db["google_trends"]
analyst_coll = db["analyst_ratings"]
news_coll = db["news_headlines"]
insider_buy_coll = db["insider_buying"]
reddit_coll = db["reddit_mentions"]
sp500_coll = db["sp500_index"]
universe_coll = db["universe"]
ticker_score_coll = db["ticker_scores"]
top_score_coll = db["top_scores"]
log_coll = db["system_logs"]
vol_mom_coll = db["volatility_momentum"]
lev_sector_coll = db["leveraged_sector_momentum"]
sector_mom_coll = db["sector_momentum_weekly"]
smallcap_mom_coll = db["smallcap_momentum_weekly"]
upgrade_mom_coll = db["upgrade_momentum_weekly"]
returns_coll = db["returns"]
risk_stats_coll = db["risk_stats"]
risk_rules_coll = db["risk_rules"]
risk_alerts_coll = db["risk_alerts"]
jobs_coll = db["jobs"]

register_db_handler(log_coll)


def clear_system_logs(days: int = 30) -> int:
    """Delete log rows older than ``days`` and return the count removed."""
    if not _pool:
        return 0
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    conn = _pool.get()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM system_logs WHERE timestamp < {PLACEHOLDER}",
                (cutoff,),
            )
            return cur.rowcount
    finally:
        _pool.put(conn)


from .backup import backup_to_github, restore_from_github  # noqa: E402
