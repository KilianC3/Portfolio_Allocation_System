import os
import datetime as dt
import asyncio
from typing import Any, Dict, Optional, List, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from service.logger import get_logger
from observability import metrics_router
from ws import ws_router
from observability.logging import LOG_DIR, clear_log_files
from database import (
    pf_coll,
    trade_coll,
    metric_coll,
    init_db,
    db,
    db_ping,
    clear_system_logs,
)
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from service.config import ALLOW_LIVE
import scripts.dashboard as scripts_dashboard
from service.scheduler import StrategyScheduler
from analytics.utils import (
    portfolio_metrics,
    portfolio_correlations,
    sector_exposures,
)
from metrics import rebalance_latency
from analytics import update_all_metrics, update_all_ticker_scores
from analytics.account import account_coll
from risk.var import historical_var, cvar
from ledger import MasterLedger
import httpx
from service.config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    AUTO_START_SCHED,
    API_TOKEN,
)


log = get_logger("api")

app = FastAPI(
    title="Portfolio Allocation API", version="1.0", openapi_url="/api/v1/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth(request: Request, call_next):
    token = request.headers.get("Authorization")
    if not token:
        token = request.query_params.get("token")
        if token:
            token = f"Bearer {token}"
    if API_TOKEN and request.url.path not in {"/health", "/readyz"}:
        if token != f"Bearer {API_TOKEN}":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


app.include_router(metrics_router)
app.include_router(ws_router)


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
                pf.set_weights(doc["weights"])
            except Exception as e:
                log.warning(f"failed to load weights for {pf.id}: {e}")


@app.on_event("startup")
async def startup_event():
    """Log when the API begins accepting requests."""
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
    pf = EquityPortfolio(data.name, gateway=AlpacaGateway(allow_live=ALLOW_LIVE))
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
    pf_coll.update_one({"_id": pf_id}, {"$set": {"weights": weights}}, upsert=True)
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
    q: Dict[str, Any] = {"portfolio_id": pf_id}
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
        for k in (
            "sharpe",
            "alpha",
            "beta",
            "max_drawdown",
            "benchmark",
            "ret_7d",
            "ret_30d",
            "ret_1y",
        ):
            if k in d:
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


@app.get("/db/{table}", response_model=None)
def read_table(
    table: str,
    limit: int = 50,
    page: int = 1,
    format: str = "json",
) -> Response | Dict[str, List[Dict[str, Any]]]:
    """Return rows from the requested table with optional pagination."""
    db_ping()
    coll = db[table]
    qry = coll.find({})
    if page > 1:
        try:
            qry.offset((page - 1) * limit)
        except AttributeError:
            pass
    qry.limit(limit)
    docs = list(qry)
    res = []
    for d in docs:
        if "_id" in d:
            d["id"] = str(d.pop("_id"))
        if "_retrieved" in d:
            d["_retrieved"] = _iso(d["_retrieved"])
        res.append(d)
    if format == "csv":
        df = pd.DataFrame(res)
        csv_data = df.to_csv(index=False)
        return Response(content=csv_data, media_type="text/csv")
    return {"records": res}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(table: str | None = None, page: int = 1, limit: int = 20) -> str:
    """Render health checks and paginated table views."""
    try:
        health_info = asyncio.run(readyz())
    except Exception as exc:
        health_info = {"status": "fail", "error": str(exc)}

    token_qs = f"&token={API_TOKEN}" if API_TOKEN else ""
    parts = ["<h2>Health</h2>", f"<pre>{health_info}</pre>"]

    if table:
        result = read_table(table, limit=limit, page=page)
        assert isinstance(result, dict)
        docs = result["records"]
        parts.append(f"<h3>{table} (page {page})</h3>")
        if docs:
            df = pd.DataFrame(docs)
            parts.append(df.to_html(index=False))
        parts.append("<p>")
        if page > 1:
            parts.append(
                f'<a href="/dashboard?table={table}&page={page-1}&limit={limit}{token_qs}">Prev</a> '
            )
        parts.append(
            f'<a href="/dashboard?table={table}&page={page+1}&limit={limit}{token_qs}">Next</a>'
        )
        parts.append("</p>")
        back_link = f"/dashboard?token={API_TOKEN}" if API_TOKEN else "/dashboard"
        parts.append(f'<p><a href="{back_link}">Back</a></p>')
    else:
        jobs = list_jobs()["jobs"]
        if jobs:
            df = pd.DataFrame(jobs)
            parts.append("<h2>Schedule</h2>")
            parts.append(df.to_html(index=False))
        parts.append("<h2>Tables</h2><ul>")
        for name in scripts_dashboard.TABLES:
            parts.append(
                f'<li><a href="/dashboard?table={name}{token_qs}">{name}</a></li>'
            )
        parts.append("</ul>")

    return "\n".join(parts)


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


@app.get("/sp500_index")
def sp500_history(limit: int = 5):
    docs = list(sp500_coll.find().sort("date", -1).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["_retrieved"] = _iso(d.get("_retrieved"))
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

    uvicorn.run(app, host="0.0.0.0", port=8001)
