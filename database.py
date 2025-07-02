from pymongo import MongoClient, ASCENDING
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME
from logger import get_logger
_log = get_logger("db")

sync = MongoClient(MONGO_URI)
async_db = AsyncIOMotorClient(MONGO_URI)

db  = sync[DB_NAME]
adb = async_db[DB_NAME]

pf_coll    = db["portfolios"]
trade_coll = db["trades"]
metric_coll= db["metrics"]
cache      = db["cache"]

trade_coll.create_index([("portfolio_id",ASCENDING),("timestamp",ASCENDING)])
metric_coll.create_index([("portfolio_id",ASCENDING),("date",ASCENDING)], unique=True)
cache.create_index("expire", expireAfterSeconds=0)
