import asyncio
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from database import pf_coll, trade_coll, metric_coll
from portfolio import Portfolio
from scheduler import StrategyScheduler
from logger import get_logger

API_KEY = os.getenv("API_KEY", "changeme")

app = FastAPI(title="Portfolio Allocation API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sched = StrategyScheduler()
portfolios: Dict[str, Portfolio] = {}
log = get_logger("api")


def verify_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    return x_api_key


class PortfolioCreate(BaseModel):
    name: str = Field(..., description="Portfolio name")


class Weights(BaseModel):
    weights: Dict[str, float]


@app.on_event("startup")
async def start():
    sched.start()
    log.info("scheduler started")


@app.on_event("shutdown")
async def shutdown():
    sched.scheduler.shutdown(wait=False)
    log.info("scheduler stopped")


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/portfolio", dependencies=[Depends(verify_key)])
def create_portfolio(data: PortfolioCreate):
    pf = Portfolio(data.name)
    portfolios[pf.id] = pf
    return {"id": pf.id, "name": pf.name}


@app.get("/portfolio", dependencies=[Depends(verify_key)])
def list_portfolios():
    cur = pf_coll.find({}, {"name": 1})
    res = [{"id": str(doc.get("_id")), "name": doc.get("name")} for doc in cur]
    return {"portfolios": res}


@app.post("/portfolio/{pf_id}/weights", dependencies=[Depends(verify_key)])
def set_weights(pf_id: str, payload: Weights):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(status_code=404, detail="portfolio not found")
    try:
        pf.set_weights(payload.weights)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "weights set"}


@app.post("/portfolio/{pf_id}/rebalance", dependencies=[Depends(verify_key)])
def rebalance(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(status_code=404, detail="portfolio not found")
    pf.rebalance()
    return {"status": "rebalanced"}


@app.get("/trades/{pf_id}", dependencies=[Depends(verify_key)])
def get_trades(pf_id: str, limit: int = 50):
    cur = trade_coll.find({"portfolio_id": pf_id}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return {"trades": list(cur)}


@app.get("/metrics", dependencies=[Depends(verify_key)])
def get_metrics(pf_id: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None):
    query = {}
    if pf_id:
        query["portfolio_id"] = pf_id
    if start or end:
        query["date"] = {}
        if start:
            query["date"]["$gte"] = start
        if end:
            query["date"]["$lte"] = end
    cur = metric_coll.find(query, {"_id": 0})
    return {"metrics": list(cur)}

