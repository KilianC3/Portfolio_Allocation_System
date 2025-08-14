from __future__ import annotations

"""Background tasks for risk analytics."""

import datetime as dt
import operator
from typing import Callable, Dict

import pandas as pd

from database import (
    returns_coll,
    risk_stats_coll,
    risk_rules_coll,
    risk_alerts_coll,
    sp500_coll,
)
from risk.var import historical_var, cvar

ALLOWED_OPERATORS = {">", "<", ">=", "<="}
ALLOWED_METRICS = {
    "var95",
    "var99",
    "es95",
    "es99",
    "vol30d",
    "beta30d",
    "max_drawdown",
}


def _load_returns(strategy: str, days: int = 60) -> pd.Series:
    q = {"strategy": strategy}
    rows = list(returns_coll.find(q).sort("date", -1).limit(days))
    if not rows:
        return pd.Series(dtype=float)
    rows.reverse()
    dates = [pd.to_datetime(r["date"]) for r in rows]
    return pd.Series([r["return_pct"] for r in rows], index=dates)


def _sp500_returns(days: int = 60) -> pd.Series:
    rows = list(sp500_coll.find().sort("date", -1).limit(days + 1))
    if not rows:
        return pd.Series(dtype=float)
    rows.sort(key=lambda r: r["date"])
    closes = pd.Series(
        [r["close"] for r in rows], index=[pd.to_datetime(r["date"]) for r in rows]
    )
    rets = closes.pct_change().dropna()
    return rets.tail(days)


def compute_risk_stats(days: int = 60) -> None:
    """Populate ``risk_stats`` table from ``returns``."""
    if not returns_coll.conn:
        return
    with returns_coll.conn.cursor() as cur:
        cur.execute("SELECT DISTINCT strategy FROM returns")
        strategies = [r["strategy"] for r in cur.fetchall()]
    bench = _sp500_returns(days)
    for strat in strategies:
        ser = _load_returns(strat, days)
        if ser.empty:
            continue
        var95 = historical_var(ser, 0.95)
        var99 = historical_var(ser, 0.99)
        es95 = cvar(ser, 0.95)
        es99 = cvar(ser, 0.99)
        vol30 = (
            float(ser.rolling(30).std().iloc[-1])
            if len(ser) >= 30
            else float(ser.std())
        )
        beta = float(ser.cov(bench) / bench.var()) if not bench.empty else 0.0
        cum = (1 + ser).cumprod()
        peak = cum.cummax()
        drawdown = (cum / peak - 1).min()
        risk_stats_coll.update_one(
            {"strategy": strat, "date": ser.index[-1].date()},
            {
                "$set": {
                    "var95": var95,
                    "var99": var99,
                    "es95": es95,
                    "es99": es99,
                    "vol30d": vol30,
                    "beta30d": beta,
                    "max_drawdown": float(drawdown),
                }
            },
            upsert=True,
        )


def evaluate_risk_rules() -> None:
    """Evaluate risk rules against latest statistics and log alerts."""
    if not risk_rules_coll.conn:
        return
    rows = list(risk_rules_coll.find())
    if not rows:
        return
    latest_stats: Dict[str, Dict[str, float]] = {}
    for r in rows:
        strat = r["strategy"]
        if strat not in latest_stats:
            stat = risk_stats_coll.find_one({"strategy": strat}, sort=[("date", -1)])
            latest_stats[strat] = stat or {}
        stat = latest_stats[strat]
        metric_val = stat.get(r["metric"])
        if metric_val is None:
            continue
        op_map: Dict[str, Callable[[float, float], bool]] = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
        }
        if r["operator"] not in ALLOWED_OPERATORS or r["metric"] not in ALLOWED_METRICS:
            continue
        func = op_map.get(r["operator"])
        if func and func(metric_val, r["threshold"]):
            risk_alerts_coll.insert_many(
                [
                    {
                        "rule_id": r["_id"],
                        "strategy": strat,
                        "metric_value": float(metric_val),
                        "triggered_at": dt.datetime.utcnow(),
                        "is_acknowledged": False,
                    }
                ]
            )


__all__ = [
    "compute_risk_stats",
    "evaluate_risk_rules",
    "ALLOWED_OPERATORS",
    "ALLOWED_METRICS",
]
