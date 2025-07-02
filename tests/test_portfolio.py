from unittest.mock import MagicMock
from portfolio import Portfolio


def test_set_weights_sum_error():
    p = Portfolio('test')
    try:
        p.set_weights({'AAPL': 0.8, 'GOOG': 0.3})
    except ValueError:
        pass
    else:
        assert False, 'expected error'


def test_rebalance_calls_execution(monkeypatch):
    p = Portfolio('t2')
    p.exec.order_to_pct = MagicMock(return_value=MagicMock(symbol='AAPL', side='buy', qty=1, filled_avg_price=10))
    p.weights = {'AAPL': 1.0}
    inserted = {}
    monkeypatch.setattr('database.trade_coll.insert_one', lambda d: inserted.update(d))
    p.rebalance()
    assert inserted['symbol'] == 'AAPL'
