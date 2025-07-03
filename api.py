import datetime as dt
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from logger import get_logger
from database import pf_coll, trade_coll, metric_coll
from portfolio import Portfolio
from scheduler import StrategyScheduler
from analytics import portfolio_metrics


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

# Scheduler instance to manage strategy tasks
sched = StrategyScheduler()

class ScheduleJob(BaseModel):
    pf_id: str
    name: str
    module: str
    cls: str
    cron_key: str

class PortfolioCreate(BaseModel):
    name: str

class Weights(BaseModel):
    weights: Dict[str, float]

class MetricEntry(BaseModel):
    date: dt.date
    ret: float
    benchmark: Optional[float] = None

def _iso(o):
    if isinstance(o, dt.datetime):
        return o.isoformat()
    if isinstance(o, dt.date):
        return o.isoformat()
    return o

def _load_portfolios():
    for doc in pf_coll.find():
        pf = Portfolio(doc.get("name", "pf"), str(doc.get("_id")))
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
        sched.start()
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


@app.get("/positions/{pf_id}")
def get_positions(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    return {"positions": pf.positions()}

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
    update = {"ret": metric.ret}
    if metric.benchmark is not None:
        update["benchmark"] = metric.benchmark

    metric_coll.update_one(
        {"portfolio_id": pf_id, "date": metric.date},
        {"$set": update},
        upsert=True,
    )

    docs = list(metric_coll.find({"portfolio_id": pf_id}).sort("date", 1))
    r = pd.Series([d["ret"] for d in docs], index=[d["date"] for d in docs])
    bench = None
    if all("benchmark" in d for d in docs):
        bench = pd.Series(
            [d.get("benchmark", 0.0) for d in docs],
            index=[d["date"] for d in docs],
        )
    metrics = portfolio_metrics(r, bench)
    metric_coll.update_one(
        {"portfolio_id": pf_id, "date": metric.date},
        {"$set": metrics},
        upsert=True,
    )
    return {"status": "ok", "metrics": metrics}

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
    res = []
    for d in docs:
        entry = {"date": _iso(d["date"]), "ret": d["ret"]}
        for k in ("sharpe", "alpha", "beta", "max_drawdown", "benchmark"):
            if k in d:
                entry[k] = d[k]
        res.append(entry)
    return {"metrics": res}

# Scheduler management endpoints
@app.get("/scheduler/jobs")
def list_jobs():
    jobs = [
        {"id": j.id, "next_run": _iso(getattr(j, "next_run_time", None))}
        for j in sched.scheduler.get_jobs()
    ]
    return {"jobs": jobs}

@app.post("/scheduler/jobs")
def add_job(job: ScheduleJob):
    try:
        sched.add(job.pf_id, job.name, job.module, job.cls, job.cron_key)
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"status": "scheduled"}

# Data collection using dedicated scraping module
from scrapers import (
    fetch_politician_trades,
    fetch_lobbying_data,
    fetch_wiki_views,
    fetch_dc_insider_scores,
    fetch_gov_contracts,
    politician_coll,
    lobby_coll,
    wiki_collection,
    insider_coll,
    contracts_coll,
)

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

@app.post("/collect/lobbying")
async def collect_lobbying():
    data = await fetch_lobbying_data()
    return {"records": len(data)}

@app.get("/lobbying")
def show_lobbying(limit: int = 50):
    docs = list(lobby_coll.find().sort("_retrieved", -1).limit(limit))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
        res.append(d)
    return {"records": res}

@app.post("/collect/wiki_views")
async def collect_wiki():
    data = await fetch_wiki_views()
    return {"records": len(data)}

@app.get("/wiki_views")
def show_wiki(limit: int = 50):
    docs = list(wiki_collection.find().sort("_retrieved", -1).limit(limit))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
        res.append(d)
    return {"records": res}

@app.post("/collect/dc_insider")
async def collect_dc_insider():
    data = await fetch_dc_insider_scores()
    return {"records": len(data)}

@app.get("/dc_insider")
def show_dc_insider(limit: int = 50):
    docs = list(insider_coll.find().sort("_retrieved", -1).limit(limit))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
        res.append(d)
    return {"records": res}

@app.post("/collect/gov_contracts")
async def collect_contracts():
    data = await fetch_gov_contracts()
    return {"records": len(data)}

@app.get("/gov_contracts")
def show_contracts(limit: int = 50):
    docs = list(contracts_coll.find().sort("_retrieved", -1).limit(limit))
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
        res.append(d)
    return {"records": res}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
