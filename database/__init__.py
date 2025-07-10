"""Database helpers for Postgres access."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import duckdb

from logger import get_logger
from config import PG_URI, ALLOW_LIVE

_log = get_logger("db")

PLACEHOLDER = "%s"
DB_FLAVOR = "pg"

try:
    _conn = psycopg2.connect(PG_URI)
    _conn.autocommit = True
    with _conn.cursor() as cur:
        cur.execute("SELECT 1")
except Exception as e:  # pragma: no cover - db may not exist in tests
    _log.error(f"Postgres connection failed: {e}; falling back to DuckDB")
    os.makedirs("data", exist_ok=True)
    _conn = duckdb.connect("data/fallback.duckdb")
    PLACEHOLDER = "?"
    DB_FLAVOR = "duck"


def db_ping() -> bool:
    """Return True if the Postgres connection is healthy."""
    if DB_FLAVOR != "pg" or not _conn:
        return False
    try:
        with _conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:  # pragma: no cover - transient errors
        _log.error(f"Database ping failed: {exc}")
        return False


class InMemoryCollection:
    """Minimal in-memory fallback used when Postgres is unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def find_one(self, q: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = q.get("key")
        if not isinstance(key, str):
            return None
        return self._store.get(key)

    def replace_one(
        self, match: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ) -> None:
        self._store[match["key"]] = doc


class PGClient:
    def __init__(self, conn):
        self._conn = conn

    @property
    def admin(self) -> "PGClient":
        return self

    def command(self, cmd: str) -> None:
        if cmd == "ping" and self._conn:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")


class PGDatabase:
    def __init__(self, conn):
        self.conn = conn
        self.client = PGClient(conn)

    def __getitem__(self, name: str) -> "PGCollection":
        return PGCollection(self.conn, name)


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

    def sort(self, field: str, direction: int) -> "PGQuery":
        col = "id" if field == "_id" else field
        self.order = f" ORDER BY {col} {'DESC' if direction < 0 else 'ASC'}"
        return self

    def limit(self, n: int) -> "PGQuery":
        self.limit_n = n
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
        return sql, params

    def __iter__(self):
        if not self.conn:
            return iter([])
        sql, params = self._sql()
        if DB_FLAVOR == "pg":
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            cur = self.conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        for r in rows:
            if "id" in r:
                r["_id"] = r.pop("id")
        return iter(rows)

    def __next__(self):  # pragma: no cover - not used directly
        return next(iter(self))


class PGCollection:
    def __init__(self, conn, table: str):
        self.conn = conn
        self.table = table

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
        where, params = _build_where(q)
        sql = f"DELETE FROM {self.table}"
        if where:
            sql += " WHERE " + where
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def insert_many(self, docs: List[Dict[str, Any]]):
        if not self.conn or not docs:
            return
        cols = ["id" if c == "_id" else c for c in docs[0].keys()]
        values = [
            [Json(d[c]) if isinstance(d[c], (dict, list)) else d[c] for c in d]
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
        item = update.get("$set", {}).copy()
        item.update(match)
        cols = ["id" if c == "_id" else c for c in item.keys()]
        vals = [
            Json(item[k]) if isinstance(item[k], (dict, list)) else item[k]
            for k in item
        ]
        placeholders = ",".join([PLACEHOLDER] * len(cols))
        if upsert:
            if DB_FLAVOR == "pg":
                conflict = ",".join(["id" if k == "_id" else k for k in match.keys()])
                updates = ",".join([f"{c}=EXCLUDED.{c}" for c in cols])
                sql = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
                with self.conn.cursor() as cur:
                    cur.execute(sql, vals)
            else:
                sql = f"INSERT OR REPLACE INTO {self.table} ({','.join(cols)}) VALUES ({placeholders})"
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
        where, params = _build_where(q)
        sql = f"SELECT COUNT(*) FROM {self.table}"
        if where:
            sql += " WHERE " + where
        if DB_FLAVOR == "pg":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        else:
            cur = self.conn.execute(sql, params)
            row = cur.fetchone()
        return int(row[0]) if row else 0


def init_db() -> None:
    """Initialise tables from ``schema.sql`` and record schema version."""
    if not _conn:
        return

    def exec_sql(sql: str) -> None:
        if DB_FLAVOR == "duck":
            sql = (
                sql.replace("SERIAL PRIMARY KEY", "INTEGER")
                .replace("SERIAL", "INTEGER")
                .replace("JSONB", "JSON")
                .replace("TIMESTAMPTZ", "TIMESTAMP")
            )
            _conn.execute(sql)
        else:
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
    exec_sql("INSERT INTO schema_version (version) VALUES (1) ON CONFLICT DO NOTHING")


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
sp500_universe_coll = db["sp500_universe"]
sp1500_universe_coll = db["sp1500_universe"]
russell2000_universe_coll = db["russell2000_universe"]
ticker_return_coll = db["ticker_returns"]
