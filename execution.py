from alpaca_trade_api import REST
from logger import get_logger
from config import ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL
import os

_log = get_logger("exec")
MAX_NOTIONAL=25000
DAILY_LOSS=0.04
class ExecutionEngine:
    def __init__(self):
        if os.getenv("TESTING"):
            from unittest.mock import MagicMock

            self.api = MagicMock()
        else:
            self.api = REST(
                ALPACA_API_KEY,
                ALPACA_API_SECRET,
                ALPACA_BASE_URL,
                api_version="v2",
            )
    def _pv(self):
        return float(self.api.get_account().portfolio_value)
    def _price(self,s): 
        return float(self.api.get_latest_trade(s).price)
    def _risk(self,diff):
        if abs(diff)>MAX_NOTIONAL: raise ValueError("notional guard")
    def order_to_pct(self,symbol,pct):
        pv=self._pv(); tgt=pv*pct
        try: cur=float(self.api.get_position(symbol).market_value)
        except: cur=0.0
        diff=tgt-cur
        self._risk(diff)
        if abs(diff)/pv<0.0003: return None
        qty=round(diff/self._price(symbol),3)
        if qty==0: return None
        side="buy" if qty>0 else "sell"
        _log.info(f"{side} {abs(qty)} {symbol}")
        return self.api.submit_order(symbol,abs(qty),side,"market","day")
