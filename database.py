"""Database helpers for MongoDB access."""

from pymongo import MongoClient, ASCENDING
import mongomock
from logger import get_logger
from config import MONGO_URI, DB_NAME

_log = get_logger("db")

if MONGO_URI.startswith("mongomock://"):
    sync = mongomock.MongoClient()
else:
    sync = MongoClient(MONGO_URI)
db = sync[DB_NAME]

pf_coll = db["portfolios"]
trade_coll = db["trades"]
metric_coll = db["metrics"]
politician_coll = db["politician_trades"]
lobbying_coll = db["lobbying"]
wiki_coll = db["wiki_views"]
insider_coll = db["dc_insider_scores"]
contracts_coll = db["gov_contracts"]
cache = db["cache"]

trade_coll.create_index([("portfolio_id", ASCENDING), ("timestamp", ASCENDING)])
metric_coll.create_index([
    ("portfolio_id", ASCENDING),
    ("date", ASCENDING),
], unique=True)
cache.create_index("expire", expireAfterSeconds=0)
