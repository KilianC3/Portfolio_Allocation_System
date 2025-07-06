"""Database helpers for MongoDB access."""

from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from typing import cast
import mongomock
from logger import get_logger
from config import MONGO_URI, DB_NAME

_log = get_logger("db")

client: MongoClient
if MONGO_URI.startswith("mongomock://"):
    client = cast(MongoClient, mongomock.MongoClient())
else:
    client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
except Exception as e:
    _log.error(f"Mongo connection failed: {e}")

db: Database = client[DB_NAME]

pf_coll: Collection = db["portfolios"]
trade_coll: Collection = db["trades"]
metric_coll: Collection = db["metrics"]
politician_coll: Collection = db["politician_trades"]
lobbying_coll: Collection = db["lobbying"]
wiki_coll: Collection = db["wiki_views"]
insider_coll: Collection = db["dc_insider_scores"]
contracts_coll: Collection = db["gov_contracts"]
cache: Collection = db["cache"]

trade_coll.create_index([("portfolio_id", ASCENDING), ("timestamp", ASCENDING)])
metric_coll.create_index([
    ("portfolio_id", ASCENDING),
    ("date", ASCENDING),
], unique=True)
cache.create_index("expire", expireAfterSeconds=0)
