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

from service.logger import get_logger, register_db_handler
from service.config import PG_URI, ALLOW_LIVE

_log = get_logger("db")

PLACEHOLDER = "%s"

_conn: Optional[Connection] = None


try:
    parts = urlparse(PG_URI)
    _conn = pymysql.connect(
        host=parts.hostname or "localhost",
        user=parts.username or "root",
        password=parts.password or "",
        database=parts.path.lstrip("/"),
        port=parts.port or 3306,
        autocommit=True,
        cursorclass=DictCursor,
    )
    with _conn.cursor() as cur:
        cur.execute("SELECT 1")
except Exception as e:  # pragma: no cover - db may not exist in tests
    _log.error(f"MariaDB connection failed: {e}")
    _conn = None


def _ensure_conn() -> bool:
    """Ping the connection and reconnect if needed."""
    global _conn
    if not _conn:
        return False
    try:
        _conn.ping(reconnect=True)
        return True
    except Exception as exc:
        _log.error("MariaDB reconnect failed: %s", exc)
        return False


def db_ping() -> bool:
    """Return True if the MariaDB connection is healthy."""
    if not _ensure_conn():
        return False
    try:
        assert _conn is not None
        with _conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:  # pragma: no cover - transient errors
        _log.error(f"Database ping failed: {exc}")
        return False


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
    def __init__(self, conn):
        self._conn = conn

    @property
    def admin(self) -> "PGClient":
        return self

    def command(self, cmd: str) -> None:
        if cmd == "ping" and self._conn:
            db_ping()


class PGDatabase:
    def __init__(self, conn):
        self.conn = conn
        self.client = PGClient(conn)

    def __getitem__(self, name: str) -> "PGCollection":
        return PGCollection(self.conn, name, self)


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
        self, conn, table: str, where: str = "", params: Iterable[Any] | None = None
    ):
        self.conn = conn
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
        if not self.conn:
            return iter([])
        db_ping()
        sql, params = self._sql()
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        for r in rows:
            if "id" in r:
                r["_id"] = r.pop("id")
        return iter(rows)

    def __next__(self):  # pragma: no cover - not used directly
        return next(iter(self))


class PGCollection:
    def __init__(self, conn, table: str, database: PGDatabase | None = None):
        self.conn = conn
        self.table = table
        self._database = database or PGDatabase(conn)

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
        return PGQuery(self.conn, self.table, where, params)

    def delete_many(self, q: Dict[str, Any]):
        if not self.conn:
            return
        db_ping()
        where, params = _build_where(q)
        sql = f"DELETE FROM {self.table}"
        if where:
            sql += " WHERE " + where
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def insert_many(self, docs: List[Dict[str, Any]]):
        if not self.conn or not docs:
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
        sql = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES {placeholders}"
        with self.conn.cursor() as cur:
            cur.execute(sql, flat)

    def insert_one(self, doc: Dict[str, Any]):
        self.insert_many([doc])

    def update_one(
        self, match: Dict[str, Any], update: Dict[str, Any], upsert: bool = False
    ):
        if not self.conn:
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
        if upsert:
            updates = ",".join([f"{c}=VALUES({c})" for c in cols])
            sql = (
                f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {updates}"
            )
            with self.conn.cursor() as cur:
                cur.execute(sql, vals)
        else:
            set_clause = ",".join([f"{c}={PLACEHOLDER}" for c in cols])
            where, params = _build_where(match)
            sql = f"UPDATE {self.table} SET {set_clause} WHERE {where}"
            with self.conn.cursor() as cur:
                cur.execute(sql, vals + params)

    # alias used by smart_scraper
    def replace_one(
        self, match: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ):
        self.update_one(match, {"$set": doc}, upsert=upsert)

    def count_documents(self, q: Dict[str, Any]) -> int:
        """Return the number of documents matching ``q``."""
        if not self.conn:
            return 0
        db_ping()
        where, params = _build_where(q)
        sql = f"SELECT COUNT(*) AS cnt FROM {self.table}"
        if where:
            sql += " WHERE " + where
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        if not row:
            return 0
        # DictCursor returns a mapping so extract the first value safely
        return int(next(iter(row.values())))


def init_db() -> None:
    """Initialise tables from ``schema.sql`` and record schema version."""
    if not _conn:
        return

    def exec_sql(sql: str) -> None:
        with _conn.cursor() as cur:
            cur.execute(sql)

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


db = PGDatabase(_conn)

pf_coll = db["portfolios"]
trade_coll = db["trades"]
metric_coll = db["metrics"]
politician_coll = db["politician_trades"]
weight_coll = db["weight_history"]
lobbying_coll = db["lobbying"]
lobby_coll = lobbying_coll
wiki_coll = db["wiki_views"]
insider_coll = db["dc_insider_scores"]
contracts_coll = db["gov_contracts"]
alloc_log_coll = db["alloc_log"]
cache = db["cache"] if _conn else InMemoryCollection()
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

register_db_handler(log_coll)


def clear_system_logs(days: int = 30) -> int:
    """Delete log rows older than ``days`` and return the count removed."""
    if not _conn:
        return 0
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    with _conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM system_logs WHERE timestamp < {PLACEHOLDER}",
            (cutoff,),
        )
        return cur.rowcount
