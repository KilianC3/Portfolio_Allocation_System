import datetime as dt
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from importlib import import_module
from logger import get_logger
from config import CRON
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from allocation_engine import compute_weights
from database import metric_coll
from analytics import update_all_metrics, record_account

_log = get_logger("sched")


class StrategyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.portfolios = {}

    def add(self, pf_id, name, mod_path, cls_name, cron_key):
        strat_cls = getattr(import_module(mod_path), cls_name)
        pf = EquityPortfolio(name, gateway=AlpacaGateway(), pf_id=pf_id)
        self.portfolios[pf_id] = pf
        self.scheduler.add_job(
            strat_cls().build,
            "cron",
            args=[pf],
            id=pf_id,
            **CRON[cron_key],
        )

    def start(self):
        async def realloc_job():
            start = dt.datetime.utcnow() - dt.timedelta(days=90)
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
            w = compute_weights(piv)
            for pid, wt in w.items():
                pf = self.portfolios.get(pid)
                if pf:
                    new = {sym: pct * wt for sym, pct in pf.weights.items()}
                    pf.set_weights(new)
                    await pf.rebalance()

        def metrics_job():
            update_all_metrics()

        async def account_job():
            gw = AlpacaGateway()
            try:
                await record_account(gw)
            finally:
                await gw.close()

        self.scheduler.add_job(
            realloc_job, "cron", day_of_week="fri", hour=21, minute=0, id="realloc"
        )
        self.scheduler.add_job(metrics_job, "cron", hour=0, minute=5, id="metrics")
        self.scheduler.add_job(account_job, "cron", hour=0, minute=0, id="account")
        self.scheduler.start()

    def stop(self):
        """Stop all scheduled jobs without blocking."""
        self.scheduler.shutdown(wait=False)
