"""Execution gateway using async HTTP client."""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional, List, Dict

import httpx
from alpaca_trade_api.rest import REST  # retained for data helpers

from logger import get_logger
from config import ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL
from database import trade_coll
from ledger import MasterLedger
from risk import PositionRisk
from opentelemetry import trace
from metrics import trade_slippage

_log = get_logger("exec_gateway")


class ExecutionGateway:
    """Abstract execution gateway interface."""

    async def order_to_pct(
        self,
        symbol: str,
        pct: float,
        pf_id: Optional[str] = None,
        ledger: Optional[MasterLedger] = None,
        risk: Optional[PositionRisk] = None,
    ):
        raise NotImplementedError

    async def submit_batch(self, orders: List[Dict]):
        raise NotImplementedError


class AlpacaGateway(ExecutionGateway):
    """Alpaca REST implementation using httpx.AsyncClient."""

    MAX_NOTIONAL = 25_000

    def __init__(self, allow_live: bool = False) -> None:
        self.paper = "paper-api" in ALPACA_BASE_URL
        if not self.paper and not allow_live:
            raise RuntimeError(
                "Live trading endpoint configured; pass allow_live=True to enable"
            )
        self.client = httpx.AsyncClient(
            base_url=ALPACA_BASE_URL,
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY or "",
                "APCA-API-SECRET-KEY": ALPACA_API_SECRET or "",
            },
        )
        self._sem = asyncio.Semaphore(5)
        self._tracer = trace.get_tracer(__name__)

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        delay = 0.2
        async with self._sem:
            for _ in range(5):
                with self._tracer.start_as_current_span(f"{method} {path}"):
                    resp = await self.client.request(method, path, **kwargs)
                if resp.status_code != 429:
                    resp.raise_for_status()
                    return resp.json()
                await asyncio.sleep(delay)
                delay *= 2
            resp.raise_for_status()
            return resp.json()

    async def _pv(self) -> float:
        data = await self.account()
        return float(data.get("portfolio_value", 0))

    async def account(self) -> Dict:
        """Return account details from Alpaca."""
        return await self._request("GET", "/v2/account")

    async def _price(self, symbol: str) -> float:
        data = await self._request("GET", f"/v2/stocks/{symbol}/trades/latest")
        if "trade" in data and "p" in data["trade"]:
            return float(data["trade"]["p"])
        return float(data.get("price", 0))

    def _risk(self, diff: float) -> None:
        if abs(diff) > self.MAX_NOTIONAL:
            raise ValueError("notional guard")

    async def _pf_position_value(self, symbol: str, pf_id: str) -> float:
        qty = 0.0
        for d in trade_coll.find({"portfolio_id": pf_id, "symbol": symbol}):
            q = float(d.get("qty", 0))
            if d.get("side") == "sell":
                qty -= q
            else:
                qty += q
        price = await self._price(symbol)
        return qty * price

    async def submit_batch(self, orders: List[Dict]):
        return await self._request("POST", "/v2/orders/batch", json=orders)

    async def order_to_pct(
        self,
        symbol: str,
        pct: float,
        pf_id: Optional[str] = None,
        ledger: Optional[MasterLedger] = None,
        risk: Optional[PositionRisk] = None,
    ):
        pv = await self._pv()
        tgt = pv * pct
        if pf_id:
            cur = await self._pf_position_value(symbol, pf_id)
        else:
            try:
                pos = await self._request("GET", f"/v2/positions/{symbol}")
                cur = float(pos.get("market_value", 0))
            except httpx.HTTPStatusError:
                cur = 0.0
        diff = tgt - cur
        self._risk(diff)
        if abs(diff) / pv < 0.0003:
            return None
        price = await self._price(symbol)
        if price < 0.5:
            raise ValueError(f"price below 0.50 for {symbol}")
        qty = round(diff / price, 3)
        if qty == 0:
            return None
        if risk and pf_id:
            await risk.check(pf_id, symbol, qty)
        side = "buy" if qty > 0 else "sell"
        _log.info(f"{side} {abs(qty)} {symbol}")
        client_id = f"{pf_id}-{uuid.uuid4().hex[:8]}" if pf_id else None
        payload = {
            "symbol": symbol,
            "qty": abs(qty),
            "side": side,
            "type": "market",
            "time_in_force": "day",
        }
        if client_id:
            payload["client_order_id"] = client_id
        if ledger and pf_id:
            key = await ledger.reserve(pf_id, symbol, qty)
        else:
            key = None
        resp = await self._request("POST", "/v2/orders", json=payload)
        if ledger and key is not None:
            await ledger.commit(key, qty)
        try:
            fill_price = float(resp.get("filled_avg_price", price))
            slippage = (fill_price - price) / price * 10_000
            trade_slippage.observe(slippage)
        except Exception:
            trade_slippage.observe(0)
        return resp


__all__ = ["ExecutionGateway", "AlpacaGateway"]
