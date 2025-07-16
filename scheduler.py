import datetime as dt
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from importlib import import_module
from logger import get_logger
from config import CRON, ALLOW_LIVE
from core.equity import EquityPortfolio
from execution.gateway import AlpacaGateway
from analytics.allocation_engine import compute_weights
from database import metric_coll
from analytics import update_all_metrics, record_account, update_all_ticker_scores

_log = get_logger("sched")


class StrategyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.portfolios = {}
        self.last_weights: dict[str, float] = {}

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
            ticker_job, "cron", day_of_week="sun", hour=6, minute=0, id="ticker_scores"
        )
        self.scheduler.add_job(account_job, "cron", hour=0, minute=0, id="account")
        self.scheduler.start()

    def stop(self):
        """Stop all scheduled jobs without blocking."""
        self.scheduler.shutdown(wait=False)
