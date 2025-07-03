import datetime as dt
from typing import Dict, List, Optional

import requests
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from logger import get_logger
from database import pf_coll, trade_coll, metric_coll
from portfolio import Portfolio

log = get_logger("api")

app = FastAPI(title="Portfolio Allocation API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory portfolio objects
portfolios: Dict[str, Portfolio] = {}

class PortfolioCreate(BaseModel):
    name: str

class Weights(BaseModel):
    weights: Dict[str, float]

class MetricEntry(BaseModel):
    date: dt.date
    ret: float

def _iso(o):
    if isinstance(o, dt.datetime):
        return o.isoformat()
    if isinstance(o, dt.date):
        return o.isoformat()
    return o

def _load_portfolios():
    for doc in pf_coll.find():
        pf = Portfolio(doc.get("name", "pf"))
        pf.id = str(doc.get("_id"))
        portfolios[pf.id] = pf
        if "weights" in doc:
            try:
                pf.set_weights(doc["weights"])
            except Exception as e:
                log.warning(f"failed to load weights for {pf.id}: {e}")

@app.on_event("startup")
def startup_event():
    try:
        _load_portfolios()
    except Exception as e:
        log.warning(f"startup load failed: {e}")
    log.info("api ready")

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/portfolios")
def list_portfolios():
    docs = list(pf_coll.find({}, {"name": 1, "weights": 1}))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["weights"] = d.get("weights", {})
        res.append(d)
    return {"portfolios": res}

@app.post("/portfolios")
def create_portfolio(data: PortfolioCreate):
    pf = Portfolio(data.name)
    portfolios[pf.id] = pf
    pf_coll.update_one({"_id": pf.id}, {"$set": {"name": data.name}}, upsert=True)
    return {"id": pf.id, "name": data.name}

@app.put("/portfolios/{pf_id}/weights")
def set_weights(pf_id: str, data: Weights):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    pf.set_weights(data.weights)
    pf_coll.update_one({"_id": pf_id}, {"$set": {"weights": data.weights}}, upsert=True)
    return {"status": "ok"}

@app.post("/portfolios/{pf_id}/rebalance")
def rebalance(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    pf.rebalance()
    return {"status": "ok"}

@app.get("/trades/{pf_id}")
def get_trades(pf_id: str, limit: int = 50):
    docs = list(trade_coll.find({"portfolio_id": pf_id}).sort("timestamp", -1).limit(limit))
    res = []
    for d in docs:
        d.pop("portfolio_id", None)
        d["id"] = str(d.pop("_id"))
        d["timestamp"] = _iso(d.get("timestamp"))
        res.append(d)
    return {"trades": res}

@app.post("/metrics/{pf_id}")
def add_metric(pf_id: str, metric: MetricEntry):
    metric_coll.update_one(
        {"portfolio_id": pf_id, "date": metric.date},
        {"$set": {"ret": metric.ret}},
        upsert=True,
    )
    return {"status": "ok"}

@app.get("/metrics/{pf_id}")
def get_metrics(pf_id: str, start: Optional[str] = None, end: Optional[str] = None):
    q = {"portfolio_id": pf_id}
    if start or end:
        q["date"] = {}
    if start:
        q["date"]["$gte"] = dt.date.fromisoformat(start)
    if end:
        q["date"]["$lte"] = dt.date.fromisoformat(end)
    docs = list(metric_coll.find(q).sort("date", 1))
    res = [
        {"date": _iso(d["date"]), "ret": d["ret"]}
        for d in docs
    ]
    return {"metrics": res}

# Example data collection using Quiver API
from config import QUIVER_API_KEY, QUIVER_RATE_SEC
from infra.rate_limiter import AsyncRateLimiter
from database import db

politician_coll = db["politician_trades"] if db else pf_coll  # fallback for tests
rate = AsyncRateLimiter(1, QUIVER_RATE_SEC)

async def fetch_politician_trades() -> List[dict]:
    if not QUIVER_API_KEY:
        raise RuntimeError("QUIVER_API_KEY not set")
    url = "https://api.quiverquant.com/beta/politician/trades"
    headers = {"accept": "application/json", "x-api-key": QUIVER_API_KEY}
    async with rate:
        resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    now = dt.datetime.utcnow()
    for item in data:
        item["_retrieved"] = now
        politician_coll.update_one({"id": item.get("id")}, {"$set": item}, upsert=True)
    return data

@app.post("/collect/politician_trades")
async def collect_politician():
    data = await fetch_politician_trades()
    return {"records": len(data)}

@app.get("/politician_trades")
def show_politician(limit: int = 50):
    docs = list(politician_coll.find().sort("_retrieved", -1).limit(limit))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
        res.append(d)
    return {"trades": res}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
