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

CRON = {
    "monthly": {"day": "1",  "hour": 3, "minute": 0},
    "weekly" : {"day_of_week": "mon", "hour": 3, "minute": 0},
}
