from decimal import Decimal
from datetime import datetime

from congress_portfolio import (
    Position,
    TradeEvent,
    apply_trade,
    mark_to_market,
    init_pelosi_portfolio,
    init_capito_portfolio,
    pelosi_seed,
    capito_seed,
)


def _sum_weights(pf):
    return sum(p.pct_alloc for p in pf.values())


def test_apply_trade_buy_rebalance():
    pf = {
        "A": Position("A", Decimal("100")),
        "B": Position("B", Decimal("100")),
    }
    apply_trade(TradeEvent("__init__", "BUY", Decimal("0"), datetime.utcnow()), pf)
    apply_trade(TradeEvent("C", "BUY", Decimal("100"), datetime.utcnow()), pf)
    assert set(pf) == {"A", "B", "C"}
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.01")


def test_apply_trade_sell_close():
    pf = {
        "A": Position("A", Decimal("100")),
        "B": Position("B", Decimal("50")),
    }
    apply_trade(TradeEvent("__init__", "BUY", Decimal("0"), datetime.utcnow()), pf)
    apply_trade(TradeEvent("B", "SELL", Decimal("25"), datetime.utcnow()), pf)
    assert pf["B"].market_value == Decimal("25")
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.01")
    apply_trade(TradeEvent("A", "CLOSE", Decimal("0"), datetime.utcnow()), pf)
    assert "A" not in pf
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.01")


def test_mark_to_market_rebalance():
    pf = {
        "A": Position("A", Decimal("100")),
        "B": Position("B", Decimal("100")),
    }
    apply_trade(TradeEvent("__init__", "BUY", Decimal("0"), datetime.utcnow()), pf)
    prices = {
        "A": {"old": Decimal("10"), "last": Decimal("20")},
        "B": {"old": Decimal("5"), "last": Decimal("5")},
    }
    mark_to_market(pf, prices)
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.01")


def test_init_pelosi_portfolio():
    pf = init_pelosi_portfolio()
    assert set(pf) == set(pelosi_seed)
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.01")


def test_init_capito_portfolio():
    pf = init_capito_portfolio()
    assert set(pf) == set(capito_seed)
    assert abs(_sum_weights(pf) - Decimal("100.00")) <= Decimal("0.05")
