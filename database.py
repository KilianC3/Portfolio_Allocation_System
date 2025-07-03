"""Database helpers.

This module normally connects to MongoDB using ``pymongo``. During test runs we
avoid establishing a real connection by providing dummy objects when the
environment variable ``TESTING`` is set.  This allows importing modules that
depend on ``database`` without requiring a running MongoDB instance.
"""

import os
from pymongo import MongoClient, ASCENDING
from logger import get_logger
from config import MONGO_URI, DB_NAME

_log = get_logger("db")

if os.getenv("TESTING"):
    from unittest.mock import MagicMock

    _log.info("Using mocked database collections")

    class DummyCollection(MagicMock):
        def create_index(self, *_args, **_kwargs):
            return None

    pf_coll = DummyCollection(name="pf_coll")
    trade_coll = DummyCollection(name="trade_coll")
    metric_coll = DummyCollection(name="metric_coll")
    politician_coll = DummyCollection(name="politician_coll")
    lobbying_coll = DummyCollection(name="lobbying_coll")
    wiki_coll = DummyCollection(name="wiki_coll")
    insider_coll = DummyCollection(name="insider_coll")
    contracts_coll = DummyCollection(name="contracts_coll")
    cache = DummyCollection(name="cache")
    db = None
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
