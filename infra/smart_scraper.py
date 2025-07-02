import asyncio, hashlib, random, datetime as dt, requests
from infra.rate_limiter import AsyncRateLimiter
from database import cache
USER_AGENTS = ["Mozilla/5.0","Chrome/122.0"]
RATE = AsyncRateLimiter(12,60)
TTL=900
async def get(url:str)->str:
    k=hashlib.md5(url.encode()).hexdigest()
    doc=cache.find_one({"key":k})
    if doc and doc["expire"]>dt.datetime.utcnow():
        return doc["payload"]
    async with RATE:
        r=requests.get(url,headers={"User-Agent":random.choice(USER_AGENTS)},timeout=15)
        if r.status_code==200:
            cache.replace_one({"key":k},{"key":k,"payload":r.text,"expire":dt.datetime.utcnow()+dt.timedelta(seconds=TTL)},upsert=True)
            return r.text
        raise RuntimeError(f"Failed {url} {r.status_code}")
