import datetime as dt
import asyncio
import threading
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from importlib import import_module
from service.logger import get_logger
from service.config import CRON, ALLOW_LIVE
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from analytics.allocation_engine import compute_weights
from database import metric_coll
from analytics import update_all_metrics, record_account, update_all_ticker_scores
from scrapers.wallstreetbets import fetch_wsb_mentions
from scrapers import full_fundamentals

_log = get_logger("sched")


class StrategyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.portfolios = {}
        self.last_weights: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

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

        self.scheduler.add_job(
            realloc_job, "cron", day_of_week="fri", hour=21, minute=0, id="realloc"
        )
        self.scheduler.add_job(metrics_job, "cron", hour=0, minute=5, id="metrics")
        self.scheduler.add_job(
            ticker_job,
            "cron",
            id="ticker_scores",
            **CRON["monthly"],
        )

        async def fundamentals_job():
            await asyncio.to_thread(full_fundamentals.main)

        run_time = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        self.scheduler.add_job(
            fundamentals_job,
            "date",
            run_date=run_time,
            id="full_fundamentals",
        )
        self.scheduler.add_job(
            wsb_job,
            "cron",
            id="wsb_mentions",
            **CRON["monthly"],
        )
        self.scheduler.add_job(account_job, "cron", hour=0, minute=0, id="account")
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
