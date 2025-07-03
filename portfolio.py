import uuid, math, datetime as dt
from typing import Dict
from logger import get_logger
from database import trade_coll, pf_coll
from execution import ExecutionEngine
_log = get_logger("portfolio")
class Portfolio:
    def __init__(self, name: str, pf_id: str | None = None):
        self.id = pf_id or str(uuid.uuid4())
        self.name = name
        self.exec = ExecutionEngine()
        self.weights = {}
        pf_coll.update_one({"_id":self.id},{"$set":{"name":self.name}},upsert=True)
    def set_weights(self,w:Dict[str,float]):
        if not math.isclose(sum(w.values()),1.0,abs_tol=1e-4):
            raise ValueError("weights must sum to 1")
        self.weights=w
        pf_coll.update_one({"_id": self.id}, {"$set": {"weights": w}}, upsert=True)
        _log.info({"set":w,"pf":self.name})
    def _log(self,order):
        trade_coll.insert_one({"portfolio_id":self.id,"timestamp":dt.datetime.utcnow(),
                               "symbol":order.symbol,"side":order.side,
                               "qty":float(order.qty),"price":float(order.filled_avg_price or 0)})
    def rebalance(self):
        current = self.positions()
        all_syms = set(current) | set(self.weights)
        for sym in all_syms:
            tgt = self.weights.get(sym, 0.0)
            ord = self.exec.order_to_pct(sym, tgt, self.id)
            if ord:
                self._log(ord)

    def positions(self) -> Dict[str, float]:
        """Aggregate positions for this portfolio based on executed trades."""
        docs = list(trade_coll.find({"portfolio_id": self.id}))
        pos: Dict[str, float] = {}
        for d in docs:
            qty = float(d.get("qty", 0))
            if d.get("side") == "sell":
                qty *= -1
            pos[d["symbol"]] = pos.get(d["symbol"], 0.0) + qty
        return pos
