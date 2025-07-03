import os
from unittest.mock import MagicMock
import pytest

from execution import ExecutionEngine, MAX_NOTIONAL
from database import trade_coll

os.environ["TESTING"] = "1"


def make_engine(pv=100000, price=10, position=None, trades=None):
    eng = ExecutionEngine()
    eng.api.get_account.return_value = MagicMock(portfolio_value=str(pv))
    eng.api.get_latest_trade.return_value = MagicMock(price=str(price))
    if position is None:
        eng.api.get_position.side_effect = Exception("no position")
    else:
        eng.api.get_position.return_value = MagicMock(market_value=str(position))
    trade_coll.find.return_value = trades or []
    return eng


def test_risk_guard():
    eng = make_engine()
    with pytest.raises(ValueError):
        eng._risk(MAX_NOTIONAL + 1)


def test_small_order_returns_none():
    eng = make_engine(pv=100000, price=50)
    order = eng.order_to_pct("AAPL", 0.0002)
    assert order is None
    eng.api.submit_order.assert_not_called()


def test_valid_order_calls_submit_with_label():
    eng = make_engine(pv=100000, price=10, trades=[])
    mock_order = MagicMock()
    eng.api.submit_order.return_value = mock_order
    order = eng.order_to_pct("AAPL", 0.1, pf_id="pfX")
    args, kwargs = eng.api.submit_order.call_args
    assert args == ("AAPL", 1000.0, "buy", "market", "day")
    assert "client_order_id" in kwargs and kwargs["client_order_id"].startswith("pfX-")
    assert order is mock_order
