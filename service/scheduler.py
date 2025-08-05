import datetime as dt
import asyncio
import threading
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from importlib import import_module
from service.logger import get_logger
from service.config import CRON, ALLOW_LIVE, SCHEDULES
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from analytics.allocation_engine import compute_weights
from database import metric_coll, jobs_coll
from analytics import update_all_metrics, record_account, update_all_ticker_scores
from scrapers.wallstreetbets import fetch_wsb_mentions
from scrapers import full_fundamentals
from scrapers.politician import fetch_politician_trades
from scrapers.lobbying import fetch_lobbying_data
from scrapers.wiki import fetch_trending_wiki_views, fetch_wiki_views
from scrapers.dc_insider import fetch_dc_insider_scores
from scrapers.gov_contracts import fetch_gov_contracts
from scrapers.app_reviews import fetch_app_reviews
from scrapers.google_trends import fetch_google_trends
from scrapers.insider_buying import fetch_insider_buying
from scrapers.momentum_weekly import (
    fetch_volatility_momentum_summary,
    fetch_leveraged_sector_summary,
    fetch_sector_momentum_summary,
    fetch_smallcap_momentum_summary,
    fetch_upgrade_momentum_summary,
)
from risk.tasks import compute_risk_stats, evaluate_risk_rules

_log = get_logger("sched")


class StrategyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.portfolios = {}
        self.last_weights: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._registered = False

    def add(self, pf_id, name, mod_path, cls_name, cron_key):
        strat_cls = getattr(import_module(mod_path), cls_name)
        pf = EquityPortfolio(
            name, gateway=AlpacaGateway(allow_live=ALLOW_LIVE), pf_id=pf_id
        )
        self.portfolios[pf_id] = pf
        self.scheduler.add_job(
            strat_cls().build,
            "cron",
            args=[pf],
            id=pf_id,
            **CRON[cron_key],
        )

    def register_jobs(self) -> None:
        """Register all configured jobs but do not start the scheduler."""
        if self._registered:
            return

        async def realloc_job():
            start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
            cur = metric_coll.find(
                {"date": {"$gte": start.date()}},
                {"portfolio_id": 1, "date": 1, "ret": 1},
            )
            df = pd.DataFrame(list(cur))
            if df.empty:
                return
            piv = df.pivot(index="date", columns="portfolio_id", values="ret").dropna(
                axis=1
            )
            weekly = (1 + piv).resample("W-FRI").prod() - 1
            weights = compute_weights(weekly, w_prev=self.last_weights)
            self.last_weights = weights
            for pid, wt in weights.items():
                pf = self.portfolios.get(pid)
                if pf:
                    new = {sym: pct * wt for sym, pct in pf.weights.items()}
                    pf.set_weights(new)
                    await pf.rebalance()

        def metrics_job():
            update_all_metrics()

        def ticker_job():
            update_all_ticker_scores()

        async def wsb_job():
            await fetch_wsb_mentions()

        async def account_job():
            gw_main = AlpacaGateway(allow_live=ALLOW_LIVE)
            try:
                await record_account(gw_main)
            finally:
                await gw_main.close()

            if ALLOW_LIVE and not gw_main.paper:
                gw_paper = AlpacaGateway(base_url="https://paper-api.alpaca.markets")
                try:
                    await record_account(gw_paper)
                finally:
                    await gw_paper.close()

        async def fundamentals_job():
            await asyncio.to_thread(full_fundamentals.main)

        async def politician_job():
            await fetch_politician_trades()

        async def lobbying_job():
            await fetch_lobbying_data()

        async def wiki_trending_job():
            await fetch_trending_wiki_views()

        async def wiki_views_job():
            await fetch_wiki_views()

        async def dc_insider_job():
            await fetch_dc_insider_scores()

        async def gov_contracts_job():
            await fetch_gov_contracts()

        async def app_reviews_job():
            await fetch_app_reviews()

        async def google_trends_job():
            await fetch_google_trends()

        async def insider_buying_job():
            await fetch_insider_buying()

        async def vol_mom_job():
            await fetch_volatility_momentum_summary()

        async def lev_sector_job():
            await fetch_leveraged_sector_summary()

        async def sector_mom_job():
            await fetch_sector_momentum_summary()

        async def smallcap_mom_job():
            await fetch_smallcap_momentum_summary()

        async def upgrade_mom_job():
            await fetch_upgrade_momentum_summary()

        job_funcs = {
            "realloc": realloc_job,
            "metrics": metrics_job,
            "ticker_scores": ticker_job,
            "wsb_mentions": wsb_job,
            "account": account_job,
            "full_fundamentals": fundamentals_job,
            "politician_trades": politician_job,
            "lobbying": lobbying_job,
            "wiki_trending": wiki_trending_job,
            "wiki_views": wiki_views_job,
            "dc_insider": dc_insider_job,
            "gov_contracts": gov_contracts_job,
            "app_reviews": app_reviews_job,
            "google_trends": google_trends_job,
            "insider_buying": insider_buying_job,
            "vol_mom": vol_mom_job,
            "lev_sector": lev_sector_job,
            "sector_mom": sector_mom_job,
            "smallcap_mom": smallcap_mom_job,
            "upgrade_mom": upgrade_mom_job,
            "risk_stats": compute_risk_stats,
            "risk_rules": evaluate_risk_rules,
        }

        for job_id, func in job_funcs.items():
            if job_id == "realloc":
                trigger = CronTrigger(day_of_week="fri", hour=21, minute=0)
                job = self.scheduler.add_job(func, trigger, id=job_id)
            elif job_id == "full_fundamentals":
                run_time = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
                job = self.scheduler.add_job(
                    func, "date", run_date=run_time, id=job_id
                )
            else:
                sched = SCHEDULES.get(job_id)
                if not sched:
                    continue
                trigger = CronTrigger.from_crontab(sched)
                job = self.scheduler.add_job(func, trigger, id=job_id)
            jobs_coll.update_one(
                {"id": job.id},
                {"$set": {"next_run": job.next_run_time}},
                upsert=True,
            )

        def _listener(event):
            job = self.scheduler.get_job(event.job_id)
            if not job:
                return
            jobs_coll.update_one(
                {"id": job.id},
                {
                    "$set": {
                        "last_run": dt.datetime.now(dt.timezone.utc),
                        "next_run": job.next_run_time,
                    }
                },
                upsert=True,
            )

        self.scheduler.add_listener(_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self._registered = True

    def start(self):
        """Start the scheduler, creating an event loop if needed."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self.scheduler.configure(event_loop=loop)
            self._thread = threading.Thread(target=loop.run_forever, daemon=True)
            self._thread.start()
        else:
            self.scheduler.configure(event_loop=loop)

        self.scheduler.start()

    def stop(self):
        """Stop all scheduled jobs without blocking."""
        self.scheduler.shutdown(wait=False)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=1)
        self._loop = None
        self._thread = None
