import os
import datetime as dt
import asyncio
import json
from typing import Any, Dict, Optional, List, Union, cast

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from service.logger import get_logger
from observability import metrics_router
from ws import ws_router
from ws.hub import (
    broadcast_message,
    register as ws_register,
    unregister as ws_unregister,
)
from service.cache import get as cache_get, set as cache_set, invalidate_prefix
from observability.logging import LOG_DIR, clear_log_files
from database import (
    pf_coll,
    trade_coll,
    metric_coll,
    weight_coll,
    alloc_perf_coll,
    alloc_log_coll,
    cache,
    PGCollection,
    account_metrics_coll,
    account_paper_coll,
    account_live_coll,
    init_db,
    db,
    db_ping,
    clear_system_logs,
    backup_to_github,
    restore_from_github,
    schema_coll,
    universe_coll,
    log_coll,
    vol_mom_coll,
    lev_sector_coll,
    sector_mom_coll,
    smallcap_mom_coll,
    upgrade_mom_coll,
    top_score_coll,
    ticker_score_coll,
    returns_coll,
    risk_stats_coll,
    risk_rules_coll,
    risk_alerts_coll,
    jobs_coll,
)
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from service.config import ALLOW_LIVE
from service.scheduler import StrategyScheduler
from analytics.utils import (
    portfolio_metrics,
    portfolio_correlations,
    sector_exposures,
    get_treasury_rate,
    get_treasury_timestamp,
)
from metrics import rebalance_latency
from analytics import update_all_metrics, update_all_ticker_scores
from analytics.account import account_coll
from risk.var import historical_var, cvar
from risk.tasks import ALLOWED_METRICS, ALLOWED_OPERATORS
from ledger import MasterLedger
import httpx
from service.config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    AUTO_START_SCHED,
    API_TOKEN,
)
import strategies


log = get_logger("api")

app = FastAPI(
    title="Portfolio Allocation API", version="1.0", openapi_url="/api/v1/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


OPEN_ENDPOINTS = {"/health", "/readyz", "/docs", "/redoc", "/api/v1/openapi.json"}


@app.middleware("http")
async def auth(request: Request, call_next):
    if request.url.path in OPEN_ENDPOINTS:
        return await call_next(request)
    token = request.headers.get("Authorization")
    if not token:
        token = request.query_params.get("token")
        if token:
            token = f"Bearer {token}"
    if not API_TOKEN:
        log.warning("API_TOKEN not set; refusing access to %s", request.url.path)
        return JSONResponse(status_code=503, content={"detail": "token not configured"})
    if token != f"Bearer {API_TOKEN}":
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


app.include_router(metrics_router)
app.include_router(ws_router)


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    """WebSocket endpoint streaming portfolio metric updates."""
    await ws_register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_unregister(ws)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    try:
        pf_coll.database.client.admin.command("ping")
        ledger = MasterLedger()
        await ledger.redis.ping()
        async with httpx.AsyncClient() as c:
            resp = await c.get(
                f"{ALPACA_BASE_URL}/v2/account",
                headers={
                    "APCA-API-KEY-ID": ALPACA_API_KEY or "",
                    "APCA-API-SECRET-KEY": ALPACA_API_SECRET or "",
                },
            )
            resp.raise_for_status()
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}
    return {"status": "ready"}


@app.get("/refresh/treasury_rate")
def refresh_treasury_rate() -> Dict[str, Any]:
    """Force refresh of the cached treasury rate."""
    rate = get_treasury_rate(force=True)
    ts = get_treasury_timestamp().isoformat()
    return {"rate": rate, "timestamp": ts}


# In-memory portfolio objects
portfolios: Dict[str, EquityPortfolio] = {}

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
    strategy: Optional[str] = None
    risk_target: Optional[float] = None
    allowed_strategies: Optional[List[str]] = None


class MetricEntry(BaseModel):
    date: dt.date
    ret: float
    benchmark: Optional[float] = None
    smb: Optional[float] = None
    hml: Optional[float] = None


class RiskRuleIn(BaseModel):
    name: str
    strategy: str
    metric: str
    operator: str
    threshold: float


def _validate_rule(rule: "RiskRuleIn") -> None:
    if rule.metric not in ALLOWED_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"metric must be one of {sorted(ALLOWED_METRICS)}",
        )
    if rule.operator not in ALLOWED_OPERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"operator must be one of {sorted(ALLOWED_OPERATORS)}",
        )


def _iso(o):
    if isinstance(o, dt.datetime):
        return o.isoformat()
    if isinstance(o, dt.date):
        return o.isoformat()
    return o


def load_portfolios():
    for doc in pf_coll.find():
        pf = EquityPortfolio(
            doc.get("name", "pf"),
            gateway=AlpacaGateway(allow_live=ALLOW_LIVE),
            pf_id=str(doc.get("_id")),
        )
        portfolios[pf.id] = pf
        if "weights" in doc:
            try:
                pf.set_weights(
                    doc["weights"],
                    strategy=doc.get("strategy"),
                    risk_target=doc.get("risk_target"),
                )
            except Exception as e:
                log.warning(f"failed to load weights for {pf.id}: {e}")


@app.on_event("startup")
async def startup_event():
    """Log readiness and register scheduler jobs."""
    log.info("api ready")
    sched.register_jobs()
    if AUTO_START_SCHED:
        sched.start()
        log.info("scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Release gateway resources for all portfolios."""
    for pf in portfolios.values():
        try:
            await pf.close()
        except Exception as exc:
            log.warning("gateway close failed for %s: %s", pf.id, exc)


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/portfolios")
def list_portfolios():
    docs = list(
        pf_coll.find(
            {},
            {
                "name": 1,
                "weights": 1,
                "strategy": 1,
                "risk_target": 1,
                "allowed_strategies": 1,
            },
        )
    )
    res = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["weights"] = d.get("weights", {})
        if "strategy" in d:
            d["strategy"] = d.get("strategy")
        if "risk_target" in d:
            d["risk_target"] = d.get("risk_target")
        if "allowed_strategies" in d:
            d["allowed_strategies"] = d.get("allowed_strategies")
        res.append(d)
    return {"portfolios": res}


@app.get("/strategies/summary")
def strategies_summary() -> Dict[str, Any]:
    docs = list(
        pf_coll.find(
            {},
            {
                "name": 1,
                "weights": 1,
                "strategy": 1,
                "risk_target": 1,
                "allowed_strategies": 1,
            },
        )
    )
    res: List[Dict[str, Any]] = []
    for d in docs:
        pf_id = str(d.get("_id"))
        metric_doc = (
            metric_coll.find_one({"portfolio_id": pf_id}, sort=[("date", -1)]) or {}
        )
        risk_doc = (
            risk_stats_coll.find_one({"strategy": pf_id}, sort=[("date", -1)]) or {}
        )
        res.append(
            {
                "id": pf_id,
                "name": d.get("name"),
                "weights": d.get("weights", {}),
                "strategy": d.get("strategy"),
                "risk_target": d.get("risk_target"),
                "allowed_strategies": d.get("allowed_strategies"),
                "metrics": {
                    k: _iso(v) if k == "date" else v
                    for k, v in metric_doc.items()
                    if k not in {"_id", "portfolio_id"}
                },
                "risk": {
                    k: _iso(v) if k == "date" else v
                    for k, v in risk_doc.items()
                    if k not in {"_id", "strategy"}
                },
            }
        )
    return {"strategies": res}


@app.get("/strategies")
def list_strategies() -> Dict[str, List[str]]:
    """Return the names of all available strategy classes."""
    return {"strategies": list(getattr(strategies, "__all__", []))}


@app.post("/portfolios")
def create_portfolio(data: PortfolioCreate):
    pf = EquityPortfolio(data.name, gateway=AlpacaGateway(allow_live=ALLOW_LIVE))
    portfolios[pf.id] = pf
    pf_coll.update_one({"_id": pf.id}, {"$set": {"name": data.name}}, upsert=True)
    return {"id": pf.id, "name": data.name}


@app.put("/portfolios/{pf_id}/weights")
def set_weights(pf_id: str, data: Weights):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    try:
        pf.set_weights(
            data.weights,
            strategy=data.strategy,
            risk_target=data.risk_target,
            allowed_strategies=data.allowed_strategies,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    update_doc: Dict[str, Any] = {
        "weights": data.weights,
        "strategy": data.strategy,
        "risk_target": data.risk_target,
    }
    if data.allowed_strategies is not None:
        update_doc["allowed_strategies"] = data.allowed_strategies

    pf_coll.update_one({"_id": pf_id}, {"$set": update_doc}, upsert=True)
    return {"status": "ok"}


@app.post("/portfolios/{pf_id}/rebalance")
async def rebalance(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    with rebalance_latency.labels(pf_id=pf_id).time():
        await pf.rebalance()
    return {"status": "ok"}


@app.get("/positions/{pf_id}")
def get_positions(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    return {"positions": pf.positions()}


@app.post("/close/{pf_id}/{symbol}")
async def close_position(pf_id: str, symbol: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    weights = pf.weights.copy()
    weights.pop(symbol, None)
    pf.set_weights(weights)
    await asyncio.to_thread(
        pf_coll.update_one,
        {"_id": pf_id},
        {"$set": {"weights": weights}},
        True,
    )
    await pf.rebalance()
    return {"status": "closed"}


@app.get("/trades/{pf_id}")
def get_trades(pf_id: str, limit: int = 50):
    docs = list(
        trade_coll.find({"portfolio_id": pf_id}).sort("timestamp", -1).limit(limit)
    )
    res = []
    for d in docs:
        d.pop("portfolio_id", None)
        d["id"] = str(d.pop("_id"))
        d["timestamp"] = _iso(d.get("timestamp"))
        res.append(d)
    return {"trades": res}


@app.get("/weight_history/{pf_id}")
def get_weight_history(pf_id: str, limit: int = 50) -> Dict[str, Any]:
    docs = list(weight_coll.find({"portfolio_id": pf_id}).sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "date" in d:
            d["date"] = _iso(d["date"])
    return {"weights": docs}


@app.get("/allocation_performance")
def get_allocation_performance(limit: int = 50) -> Dict[str, Any]:
    docs = list(alloc_perf_coll.find().sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "date" in d:
            d["date"] = _iso(d["date"])
    return {"records": docs}


@app.post("/metrics/{pf_id}")
def add_metric(pf_id: str, metric: MetricEntry):
    update = {"ret": metric.ret}
    if metric.benchmark is not None:
        update["benchmark"] = metric.benchmark
    if metric.smb is not None:
        update["smb"] = metric.smb
    if metric.hml is not None:
        update["hml"] = metric.hml

    metric_coll.update_one(
        {"portfolio_id": pf_id, "date": metric.date},
        {"$set": update},
        upsert=True,
    )

    docs = list(metric_coll.find({"portfolio_id": pf_id}).sort("date", 1))
    r = pd.Series([d["ret"] for d in docs], index=[d["date"] for d in docs])
    factors = None
    if all("benchmark" in d for d in docs):
        factors = pd.DataFrame(
            {"mkt": [d.get("benchmark", 0.0) for d in docs]},
            index=[d["date"] for d in docs],
        )
        if all("smb" in d for d in docs) and all("hml" in d for d in docs):
            factors["smb"] = [d.get("smb", 0.0) for d in docs]
            factors["hml"] = [d.get("hml", 0.0) for d in docs]
    rf = get_treasury_rate()
    metrics = portfolio_metrics(r, factors, rf)
    metric_coll.update_one(
        {"portfolio_id": pf_id, "date": metric.date},
        {"$set": metrics},
        upsert=True,
    )
    invalidate_prefix(f"metrics:{pf_id}")
    message = json.dumps(
        {
            "type": "metrics",
            "portfolio_id": pf_id,
            "date": metric.date.isoformat(),
            "metrics": metrics,
        }
    )
    asyncio.create_task(broadcast_message(message))
    return {"status": "ok", "metrics": metrics}


@app.get("/metrics/{pf_id}")
def get_metrics(pf_id: str, start: Optional[str] = None, end: Optional[str] = None):
    q: Dict[str, Any] = {"portfolio_id": pf_id}
    if start or end:
        q["date"] = {}
    if start:
        q["date"]["$gte"] = dt.date.fromisoformat(start)
    if end:
        q["date"]["$lte"] = dt.date.fromisoformat(end)
    cache_key = f"metrics:{pf_id}:{start or ''}:{end or ''}"
    docs = cache_get(cache_key)
    if docs is None:
        docs = list(metric_coll.find(q).sort("date", 1))
        cache_set(cache_key, docs)
    res = []
    for d in docs:
        entry = {"date": _iso(d["date"]), "ret": d["ret"]}
        for k in (
            "sharpe",
            "alpha",
            "beta",
            "ff_expected_return",
            "beta_smb",
            "beta_hml",
            "max_drawdown",
            "var",
            "cvar",
            "benchmark",
            "exposure",
            "win_rate",
            "annual_vol",
            "ret_7d",
            "ret_30d",
            "ret_1y",
        ):
            if k in d:
                if k == "annual_vol":
                    entry["volatility"] = d[k]
                else:
                    entry[k] = d[k]
        res.append(entry)
    return {"metrics": res}


@app.post("/collect/metrics")
def collect_all_metrics(days: int = 90):
    update_all_metrics(days)
    return {"status": "ok"}


@app.get("/logs")
def get_logs(lines: int = 100):
    path = os.path.join(LOG_DIR, "app.log")
    try:
        from collections import deque

        with open(path) as f:
            tail = "".join(deque(f, maxlen=lines))
    except Exception:
        tail = ""
    return {"logs": tail}


@app.delete("/logs")
def delete_logs(days: int = 30):
    """Remove old log entries and log files."""
    removed = clear_system_logs(days)
    clear_log_files()
    return {"deleted": removed}


@app.get("/system_logs")
def show_system_logs(limit: int = 100, format: str = "json"):
    docs = list(log_coll.find().sort("timestamp", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["timestamp"] = _iso(d.get("timestamp"))
    df = pd.DataFrame(docs)
    records = df.to_dict(orient="records")
    message = json.dumps({"type": "logs", "records": records})
    asyncio.create_task(broadcast_message(message))
    if format == "csv":
        csv_data = df.to_csv(index=False)
        return Response(content=csv_data, media_type="text/csv")
    return {"records": records}


@app.get("/schema_version")
def get_schema_version() -> Dict[str, int]:
    doc = schema_coll.find_one(sort=[("version", -1)]) if schema_coll else None
    return {"version": doc.get("version") if doc else 0}


@app.get("/db")
def list_tables() -> Dict[str, List[str]]:
    """Return the list of available database tables."""
    db_ping()
    if not db.conn:
        return {"tables": []}
    with db.conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute("SHOW TABLES")
        rows = cur.fetchall()
    tables = [next(iter(r.values())) for r in rows]
    # Ensure the log table is visible even if created separately
    if "system_logs" not in tables:
        tables.append("system_logs")
    return {"tables": tables}


@app.get("/db/{table}", response_model=None)
def read_table(
    table: str,
    limit: int = 50,
    page: int = 1,
    format: str = "json",
    sort_by: Optional[str] = None,
    order: str = "asc",
    fields: Optional[str] = None,
) -> Response | Dict[str, List[Dict[str, Any]]]:
    """Return rows from the requested table with optional pagination."""
    db_ping()
    coll = db[table]
    projection = None
    if fields:
        projection = {
            f: 1 for f in [fld.strip() for fld in fields.split(",") if fld.strip()]
        }
        projection["_id"] = 1
    qry = coll.find({}, projection)
    if sort_by:
        direction = order.lower()
        if direction not in {"asc", "desc"}:
            raise HTTPException(400, "invalid order")
        qry = qry.sort(sort_by, 1 if direction == "asc" else -1)
    elif order.lower() not in {"asc", "desc"}:
        raise HTTPException(400, "invalid order")
    if page > 1:
        try:
            qry.offset((page - 1) * limit)
        except AttributeError:
            pass
    qry.limit(limit)
    docs = list(qry)
    for d in docs:
        if "_id" in d:
            d["id"] = str(d.pop("_id"))
        if "_retrieved" in d:
            d["_retrieved"] = _iso(d["_retrieved"])
    df = pd.DataFrame(docs)
    if format == "csv":
        csv_data = df.to_csv(index=False)
        return Response(content=csv_data, media_type="text/csv")
    return {"records": df.to_dict(orient="records")}


@app.delete("/db/system_logs")
def clear_db_logs(days: int = 30) -> Dict[str, int]:
    """Remove log rows older than ``days`` and return the count deleted."""
    removed = clear_system_logs(days)
    return {"removed": removed}


@app.post("/db/backup")
def backup_db() -> Dict[str, str]:
    """Dump all tables and commit the snapshot to git."""
    backup_to_github()
    return {"status": "ok"}


@app.post("/db/restore")
def restore_db() -> Dict[str, int]:
    """Pull the latest backup from git and restore tables."""
    restored = restore_from_github()
    return {"restored": restored}


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


@app.post("/scheduler/start")
def start_scheduler():
    sched.start()
    return {"status": "started"}


@app.post("/scheduler/stop")
def stop_scheduler():
    sched.stop()
    return {"status": "stopped"}


# Job status endpoints
@app.get("/jobs")
def list_job_status():
    docs = list(jobs_coll.find({}))
    res = []
    for d in docs:
        d["id"] = d.get("id", str(d.get("_id")))
        d["last_run"] = _iso(d.get("last_run"))
        d["next_run"] = _iso(d.get("next_run"))
        res.append(d)
    return {"jobs": res}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    doc = jobs_coll.find_one({"id": job_id})
    if not doc:
        raise HTTPException(404, "job not found")
    doc["id"] = job_id
    doc["last_run"] = _iso(doc.get("last_run"))
    doc["next_run"] = _iso(doc.get("next_run"))
    return doc


@app.post("/jobs/{job_id}/run")
def run_job(job_id: str):
    try:
        sched.scheduler.modify_job(
            job_id, next_run_time=dt.datetime.now(dt.timezone.utc)
        )
    except Exception as e:
        raise HTTPException(404, str(e))
    return {"status": "triggered"}


# Data collection using dedicated scraping module
from scrapers.politician import fetch_politician_trades, politician_coll
from scrapers.lobbying import fetch_lobbying_data, lobby_coll
from scrapers.wiki import fetch_trending_wiki_views, fetch_wiki_views, wiki_collection
from scrapers.dc_insider import fetch_dc_insider_scores, insider_coll
from scrapers.gov_contracts import fetch_gov_contracts, contracts_coll
from scrapers.app_reviews import fetch_app_reviews, app_reviews_coll
from scrapers.google_trends import fetch_google_trends, trends_coll
from scrapers.wallstreetbets import fetch_wsb_mentions, reddit_coll
from scrapers.analyst_ratings import fetch_analyst_ratings, analyst_coll
from scrapers.insider_buying import fetch_insider_buying, insider_buy_coll
from scrapers.sp500_index import fetch_sp500_history, sp500_coll
from scrapers.news import fetch_stock_news, news_coll
from scrapers.volatility_momentum import fetch_volatility_momentum_summary
from scrapers.leveraged_sector_momentum import fetch_leveraged_sector_summary
from scrapers.sector_momentum import fetch_sector_momentum_summary
from scrapers.smallcap_momentum import fetch_smallcap_momentum_summary
from scrapers.upgrade_momentum import fetch_upgrade_momentum_summary
from scrapers.universe import load_sp500, load_sp400, load_russell2000


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


@app.post("/collect/app_reviews")
async def collect_reviews():
    data = await fetch_app_reviews()
    return {"records": len(data)}


@app.get("/app_reviews")
def show_reviews(limit: int = 50):
    docs = list(app_reviews_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/google_trends")
async def collect_trends():
    data = await fetch_google_trends()
    return {"records": len(data)}


@app.get("/google_trends")
def show_trends(limit: int = 50):
    docs = list(trends_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/insider_buying")
async def collect_insider():
    data = await fetch_insider_buying()
    return {"records": len(data)}


@app.get("/insider_buying")
def show_insider(limit: int = 50):
    docs = list(insider_buy_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/news_headlines")
async def collect_news() -> Dict[str, int]:
    data = await fetch_stock_news()
    return {"records": len(data)}


@app.get("/news_headlines")
def show_news(limit: int = 50):
    docs = list(news_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/reddit_mentions")
async def collect_reddit() -> Dict[str, int]:
    data = await fetch_wsb_mentions()
    return {"records": len(data)}


@app.get("/reddit_mentions")
def show_reddit(limit: int = 50):
    docs = list(reddit_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.get("/sp500_index")
def sp500_history(limit: int = 5):
    docs = list(sp500_coll.find().sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.get("/universe")
def show_universe(index: Optional[str] = None, limit: int = 1000):
    q: Dict[str, Any] = {}
    if index:
        q["index_name"] = index
    docs = list(universe_coll.find(q).sort("ticker", 1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return {"records": docs}


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


@app.post("/collect/volatility_momentum")
async def collect_vol_mom():
    data = await asyncio.to_thread(fetch_volatility_momentum_summary)
    return {"records": len(data)}


@app.get("/volatility_momentum")
def show_vol_mom(limit: int = 50):
    docs = list(vol_mom_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/leveraged_sector_momentum")
async def collect_lev_sector():
    data = await asyncio.to_thread(fetch_leveraged_sector_summary)
    return {"records": len(data)}


@app.get("/leveraged_sector_momentum")
def show_lev_sector(limit: int = 50):
    docs = list(lev_sector_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/sector_momentum_weekly")
async def collect_sector_mom():
    data = await asyncio.to_thread(fetch_sector_momentum_summary)
    return {"records": len(data)}


@app.get("/sector_momentum_weekly")
def show_sector_mom(limit: int = 50):
    docs = list(sector_mom_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/smallcap_momentum_weekly")
async def collect_smallcap_mom():
    tickers = load_russell2000()
    data = await asyncio.to_thread(fetch_smallcap_momentum_summary, tickers)
    return {"records": len(data)}


@app.get("/smallcap_momentum_weekly")
def show_smallcap_mom(limit: int = 50):
    docs = list(smallcap_mom_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.post("/collect/upgrade_momentum_weekly")
async def collect_upgrade_mom():
    universe = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    data = await fetch_upgrade_momentum_summary(universe)
    return {"records": len(data)}


@app.get("/upgrade_momentum_weekly")
def show_upgrade_mom(limit: int = 50):
    docs = list(upgrade_mom_coll.find().sort("_retrieved", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
    return {"records": docs}


@app.get("/top_scores")
def show_top_scores(limit: int = 20):
    latest = top_score_coll.find_one(sort=[("date", -1)])
    if not latest:
        return {"records": []}
    docs = list(
        top_score_coll.find({"date": latest["date"]}).sort("rank", 1).limit(limit)
    )
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return {"records": docs}


@app.post("/collect/ticker_scores")
async def collect_ticker_scores():
    await asyncio.to_thread(update_all_ticker_scores)
    return {"status": "ok"}


@app.get("/ticker_scores")
def show_ticker_scores(symbol: Optional[str] = None, limit: int = 50):
    q: Dict[str, Any] = {}
    if symbol:
        q["symbol"] = symbol.upper()
    docs = list(ticker_score_coll.find(q).sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return {"records": docs}


@app.get("/alloc_log")
def show_alloc_log(limit: int = 50):
    docs = list(alloc_log_coll.find().sort("id", -1).limit(limit))
    for d in docs:
        d["id"] = d.get("id")
    return {"records": docs}


@app.get("/cache")
def show_cache(key: Optional[str] = None, limit: int = 50):
    q: Dict[str, Any] = {"cache_key": key} if key else {}
    coll = cast(PGCollection, cache)
    docs = list(coll.find(q).sort("expire", -1).limit(limit))
    for d in docs:
        d["id"] = d.pop("cache_key")
        if d.get("expire"):
            d["expire"] = _iso(d["expire"])
    return {"records": docs}


@app.get("/var")
def var_history(
    pf_id: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None
):
    q: Dict[str, Any] = {}
    if pf_id:
        q["portfolio_id"] = pf_id
    if start or end:
        q["date"] = {}
    if start:
        q["date"]["$gte"] = dt.date.fromisoformat(start)
    if end:
        q["date"]["$lte"] = dt.date.fromisoformat(end)
    docs = list(metric_coll.find(q).sort("date", 1))
    if not docs:
        return {"var": []}
    r = pd.Series([d["ret"] for d in docs])
    var = historical_var(r)
    cv = cvar(r)
    return {"var": var, "cvar": cv}


@app.get("/correlations")
def correlations(start: Optional[str] = None, end: Optional[str] = None):
    q: Dict[str, Any] = {}
    if start or end:
        q["date"] = {}
    if start:
        q["date"]["$gte"] = dt.date.fromisoformat(start)
    if end:
        q["date"]["$lte"] = dt.date.fromisoformat(end)
    docs = list(metric_coll.find(q))
    if not docs:
        return {"correlations": {}}
    by_pf: Dict[str, list] = {}
    for d in docs:
        pf = d["portfolio_id"]
        by_pf.setdefault(pf, []).append(d["ret"])
    df = pd.DataFrame(by_pf)
    corr = portfolio_correlations(df)
    return {"correlations": corr.to_dict()}


@app.get("/sector_exposure/{pf_id}")
def sector_exposure(pf_id: str):
    pf = portfolios.get(pf_id)
    if not pf:
        raise HTTPException(404, "portfolio not found")
    exposure = sector_exposures(pf.weights)
    return {"exposure": exposure}


@app.get("/analytics/{pf_id}")
def get_analytics(
    pf_id: str, start: Optional[str] = None, end: Optional[str] = None
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"portfolio_id": pf_id}
    if start or end:
        q["date"] = {}
    if start:
        q["date"]["$gte"] = dt.date.fromisoformat(start)
    if end:
        q["date"]["$lte"] = dt.date.fromisoformat(end)
    docs = list(metric_coll.find(q).sort("date", 1))
    if not docs:
        return {"analytics": []}
    df = pd.DataFrame(docs)
    df["rolling_30"] = df["ret"].rolling(30).mean()
    df["rolling_90"] = df["ret"].rolling(90).mean()
    return {"analytics": df.to_dict(orient="records")}


@app.get("/risk/overview")
def risk_overview(strategy: str) -> Dict[str, Any]:
    stat = risk_stats_coll.find_one({"strategy": strategy}, sort=[("date", -1)])
    series = list(risk_stats_coll.find({"strategy": strategy}).sort("date", 1))
    alerts = list(
        risk_alerts_coll.find({"strategy": strategy}).sort("triggered_at", -1).limit(20)
    )
    for a in alerts:
        a["triggered_at"] = _iso(a.get("triggered_at"))
    return {
        "var95": {
            "current": stat.get("var95") if stat else None,
            "series": [
                {"date": _iso(r["date"]), "value": r.get("var95")} for r in series
            ],
        },
        "vol30d": {
            "current": stat.get("vol30d") if stat else None,
            "series": [
                {"date": _iso(r["date"]), "value": r.get("vol30d")} for r in series
            ],
        },
        "maxDrawdown": stat.get("max_drawdown") if stat else None,
        "beta30d": stat.get("beta30d") if stat else None,
        "alerts": alerts,
    }


@app.get("/returns")
def show_returns(strategy: Optional[str] = None, limit: int = 50):
    q: Dict[str, Any] = {}
    if strategy:
        q["strategy"] = strategy
    docs = list(returns_coll.find(q).sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "date" in d:
            d["date"] = _iso(d["date"])
    return {"records": docs}


@app.get("/risk/var")
def risk_var(strategy: str, window: int = 30, conf: str = "95,99") -> Dict[str, Any]:
    levels = [c.strip() for c in conf.split(",") if c.strip()]
    rows = list(
        risk_stats_coll.find({"strategy": strategy}).sort("date", -1).limit(window)
    )
    rows.reverse()
    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"var": {}, "es": {}}
    for level in levels:
        out["var"][level] = [
            {"date": _iso(r["date"]), "value": r.get(f"var{level}")} for r in rows
        ]
        out["es"][level] = [
            {"date": _iso(r["date"]), "value": r.get(f"es{level}")} for r in rows
        ]
    return out


@app.get("/risk_stats")
def show_risk_stats(strategy: Optional[str] = None, limit: int = 50):
    q: Dict[str, Any] = {}
    if strategy:
        q["strategy"] = strategy
    docs = list(risk_stats_coll.find(q).sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "date" in d:
            d["date"] = _iso(d["date"])
    return {"records": docs}


@app.get("/risk/drawdowns")
def risk_drawdowns(strategy: str) -> Dict[str, List[Dict[str, Any]]]:
    rows = list(returns_coll.find({"strategy": strategy}).sort("date", 1))
    if not rows:
        return {"drawdowns": []}
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    cum = (1 + df["return_pct"]).cumprod()
    peak = cum.cummax()
    dd = cum / peak - 1
    drawdowns: List[Dict[str, Any]] = []
    in_dd = False
    peak_date = dd.index[0]
    trough_date = dd.index[0]
    trough_val = 0.0
    for date, val in dd.items():
        if val < 0 and not in_dd:
            in_dd = True
            peak_date = date
            trough_date = date
            trough_val = val
        elif in_dd:
            if val < trough_val:
                trough_val = val
                trough_date = date
            if val >= 0:
                drawdowns.append(
                    {
                        "peak_date": _iso(peak_date),
                        "trough_date": _iso(trough_date),
                        "depth": float(trough_val),
                        "duration": int((date - peak_date).days),
                    }
                )
                in_dd = False
    if in_dd:
        drawdowns.append(
            {
                "peak_date": _iso(peak_date),
                "trough_date": _iso(trough_date),
                "depth": float(trough_val),
                "duration": int((dd.index[-1] - peak_date).days),
            }
        )
    return {"drawdowns": drawdowns}


@app.get("/risk/volatility")
def risk_volatility(strategy: str, window: int = 30) -> Dict[str, Any]:
    rows = list(
        risk_stats_coll.find({"strategy": strategy}).sort("date", -1).limit(window)
    )
    rows.reverse()
    return {
        "series": [{"date": _iso(r["date"]), "value": r.get("vol30d")} for r in rows]
    }


@app.get("/risk/beta")
def risk_beta(
    strategy: str, benchmark: str = "SP500", window: int = 30
) -> Dict[str, Any]:
    rows = list(
        risk_stats_coll.find({"strategy": strategy}).sort("date", -1).limit(window)
    )
    rows.reverse()
    return {
        "series": [{"date": _iso(r["date"]), "value": r.get("beta30d")} for r in rows]
    }


@app.get("/risk/contribution")
def risk_contribution(strategy: str) -> Dict[str, Any]:
    return {}


@app.get("/risk/correlations")
def risk_correlations(items: str, window: int = 30) -> Dict[str, Any]:
    syms = [i for i in items.split(",") if i]
    if not syms:
        return {"correlations": {}}
    data: Dict[str, List[float]] = {}
    for s in syms:
        rows = list(returns_coll.find({"strategy": s}).sort("date", -1).limit(window))
        rows.reverse()
        data[s] = [r["return_pct"] for r in rows]
    df = pd.DataFrame(data)
    corr = df.corr().to_dict() if not df.empty else {}
    return {"correlations": corr}


@app.post("/risk/rules")
def create_rule(rule: RiskRuleIn) -> Dict[str, Any]:
    _validate_rule(rule)
    if not risk_rules_coll.conn:
        return {"id": 0}
    with risk_rules_coll.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO risk_rules (name,strategy,metric,operator,threshold) VALUES (%s,%s,%s,%s,%s)",
            (
                rule.name,
                rule.strategy,
                rule.metric,
                rule.operator,
                rule.threshold,
            ),
        )
        rid = cur.lastrowid
    return {"id": rid}


@app.get("/risk/rules")
def list_rules() -> Dict[str, Any]:
    rows = list(risk_rules_coll.find())
    for r in rows:
        if "created_at" in r:
            r["created_at"] = _iso(r["created_at"])
    return {"rules": rows}


@app.put("/risk/rules/{rule_id}")
def update_rule(rule_id: int, rule: RiskRuleIn) -> Dict[str, Any]:
    _validate_rule(rule)
    risk_rules_coll.update_one(
        {"_id": rule_id},
        {
            "$set": {
                "name": rule.name,
                "strategy": rule.strategy,
                "metric": rule.metric,
                "operator": rule.operator,
                "threshold": rule.threshold,
            }
        },
        upsert=False,
    )
    return {"updated": True}


@app.delete("/risk/rules/{rule_id}")
def delete_rule(rule_id: int) -> Dict[str, Any]:
    risk_rules_coll.delete_many({"_id": rule_id})
    return {"deleted": True}


@app.get("/risk/alerts")
def list_alerts(strategy: Optional[str] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if strategy:
        q["strategy"] = strategy
    rows = list(risk_alerts_coll.find(q).sort("triggered_at", -1).limit(50))
    for r in rows:
        if "triggered_at" in r:
            r["triggered_at"] = _iso(r["triggered_at"])
    return {"alerts": rows}


@app.websocket("/ws/risk-alerts")
async def ws_risk_alerts(ws: WebSocket) -> None:
    await ws.accept()
    last_id = 0
    while True:
        rows = list(risk_alerts_coll.find({"_id": {"$gt": last_id}}).sort("_id", 1))
        for r in rows:
            last_id = max(last_id, r.get("_id", 0))
            if "triggered_at" in r:
                r["triggered_at"] = _iso(r["triggered_at"])
            await ws.send_json(r)
        await asyncio.sleep(5)


@app.get("/risk/summary")
def risk_summary(strategies: str) -> Dict[str, Any]:
    syms = [s for s in strategies.split(",") if s]
    out: List[Dict[str, Any]] = []
    for s in syms:
        stat = risk_stats_coll.find_one({"strategy": s}, sort=[("date", -1)])
        if not stat:
            continue
        out.append(
            {
                "strategy": s,
                "var95": stat.get("var95"),
                "vol30d": stat.get("vol30d"),
                "beta30d": stat.get("beta30d"),
                "max_drawdown": stat.get("max_drawdown"),
            }
        )
    return {"summary": out}


@app.get("/account_metrics")
def show_account_metrics(limit: int = 50):
    docs = list(account_metrics_coll.find().sort("timestamp", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "timestamp" in d:
            d["timestamp"] = _iso(d["timestamp"])
    return {"records": docs}


@app.get("/account_metrics_paper")
def show_account_metrics_paper(limit: int = 50):
    docs = list(account_paper_coll.find().sort("timestamp", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "timestamp" in d:
            d["timestamp"] = _iso(d["timestamp"])
    return {"records": docs}


@app.get("/account_metrics_live")
def show_account_metrics_live(limit: int = 50):
    docs = list(account_live_coll.find().sort("timestamp", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "timestamp" in d:
            d["timestamp"] = _iso(d["timestamp"])
    return {"records": docs}


@app.get("/stream/account")
async def stream_account() -> StreamingResponse:
    async def gen():
        while True:
            doc = account_coll.find_one(sort=[("timestamp", -1)])
            if doc:
                doc["timestamp"] = _iso(doc["timestamp"])
                yield f"data: {doc}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    from service.config import API_HOST, API_PORT

    uvicorn.run(app, host=API_HOST or "0.0.0.0", port=API_PORT or 8001)
