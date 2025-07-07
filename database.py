"""Database helpers for Postgres access."""

from __future__ import annotations

import os
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from logger import get_logger
from config import PG_URI

_log = get_logger("db")

try:
    _conn = psycopg2.connect(PG_URI)
    _conn.autocommit = True
except Exception as e:  # pragma: no cover - db may not exist in tests
    _log.error(f"Postgres connection failed: {e}")
    _conn = None


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
                sub.append(f"{col}>=%s")
                params.append(v["$gte"])
            if "$lte" in v:
                sub.append(f"{col}<=%s")
                params.append(v["$lte"])
            clauses.append(" AND ".join(sub))
        else:
            clauses.append(f"{col}=%s")
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
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
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
            ["(" + ",".join(["%s"] * len(cols)) + ")" for _ in values]
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
        placeholders = ",".join(["%s"] * len(cols))
        if upsert:
            conflict = ",".join(["id" if k == "_id" else k for k in match.keys()])
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in cols])
            sql = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
            with self.conn.cursor() as cur:
                cur.execute(sql, vals)
        else:
            set_clause = ",".join([f"{c}=%s" for c in cols])
            where, params = _build_where(match)
            sql = f"UPDATE {self.table} SET {set_clause} WHERE {where}"
            with self.conn.cursor() as cur:
                cur.execute(sql, vals + params)

    # alias used by smart_scraper
    def replace_one(
        self, match: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ):
        self.update_one(match, {"$set": doc}, upsert=upsert)


def init_db() -> None:
    if not _conn:
        return
    with _conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id TEXT PRIMARY KEY,
                name TEXT,
                weights JSONB
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                portfolio_id TEXT REFERENCES portfolios(id),
                symbol TEXT,
                qty DOUBLE PRECISION,
                side TEXT,
                price DOUBLE PRECISION,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
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
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS politician_trades (
                id SERIAL PRIMARY KEY,
                politician TEXT,
                ticker TEXT,
                transaction TEXT,
                amount TEXT,
                date TEXT,
                _retrieved TIMESTAMPTZ,
                UNIQUE(politician, ticker, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lobbying (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                client TEXT,
                amount TEXT,
                date TEXT,
                _retrieved TIMESTAMPTZ,
                UNIQUE(ticker, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wiki_views (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                views TEXT,
                date TEXT,
                _retrieved TIMESTAMPTZ,
                UNIQUE(ticker, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dc_insider_scores (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                score TEXT,
                date TEXT,
                _retrieved TIMESTAMPTZ,
                UNIQUE(ticker, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gov_contracts (
                id SERIAL PRIMARY KEY,
                ticker TEXT,
                value TEXT,
                date TEXT,
                _retrieved TIMESTAMPTZ,
                UNIQUE(ticker, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alloc_log (
                id SERIAL PRIMARY KEY,
                data JSONB
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                payload TEXT,
                expire TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS account_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ,
                data JSONB
            )
            """
        )


db = PGDatabase(_conn) if _conn else None

pf_coll = db["portfolios"] if db else None
trade_coll = db["trades"] if db else None
metric_coll = db["metrics"] if db else None
politician_coll = db["politician_trades"] if db else None
lobbying_coll = db["lobbying"] if db else None
lobby_coll = lobbying_coll
wiki_coll = db["wiki_views"] if db else None
insider_coll = db["dc_insider_scores"] if db else None
contracts_coll = db["gov_contracts"] if db else None
alloc_log_coll = db["alloc_log"] if db else None
cache = db["cache"] if db else None
account_coll = db["account_metrics"] if db else None
