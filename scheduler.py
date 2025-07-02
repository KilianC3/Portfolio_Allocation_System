import asyncio, datetime as dt, pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from importlib import import_module
from logger import get_logger
from config import CRON
from portfolio import Portfolio
from allocation_engine import compute_weights
from database import metric_coll
_log = get_logger("sched")
class StrategyScheduler:
    def __init__(self):
        self.scheduler=AsyncIOScheduler(); self.portfolios={}
    def add(self,pf_id,name,mod_path,cls_name,cron_key):
        strat_cls=getattr(import_module(mod_path),cls_name)
        pf=Portfolio(name); self.portfolios[pf_id]=pf
        self.scheduler.add_job(strat_cls().build,"cron",args=[pf],id=pf_id,**CRON[cron_key])
    def start(self):
        async def realloc_job():
            start=dt.datetime.utcnow()-dt.timedelta(days=90)
            cur=metric_coll.find({"date":{"$gte":start.date()}},{"portfolio_id":1,"date":1,"ret":1})
            df=pd.DataFrame(list(cur))
            if df.empty: return
            piv=df.pivot(index="date",columns="portfolio_id",values="ret").dropna(axis=1)
            w=compute_weights(piv)
            for pid,wt in w.items():
                pf=self.portfolios.get(pid)
                if pf:
                    new={sym:pct*wt for sym,pct in pf.weights.items()}
                    pf.set_weights(new); pf.rebalance()
        self.scheduler.add_job(realloc_job,"cron",day_of_week="fri",hour=21,minute=0,id="realloc")
        self.scheduler.start()
