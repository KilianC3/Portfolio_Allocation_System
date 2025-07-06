import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

QUIVER_RATE_SEC   = float(os.getenv("QUIVER_RATE_SEC", 1.1))

MONGO_URI         = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME           = os.getenv("DB_NAME", "quant_fund")

MIN_ALLOC         = float(os.getenv("MIN_ALLOCATION", 0.02))
MAX_ALLOC         = float(os.getenv("MAX_ALLOCATION", 0.40))

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT", "WSB-Strategy/1.0")

CRON = {
    "monthly": {"day": "1",  "hour": 3, "minute": 0},
    "weekly" : {"day_of_week": "mon", "hour": 3, "minute": 0},
}
