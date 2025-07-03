from unittest.mock import patch, MagicMock
from scheduler import StrategyScheduler


class DummyOrder:
    def __init__(self, symbol):
        self.symbol = symbol
        self.side = 'buy'
        self.qty = 1
        self.filled_avg_price = 10


def test_strategy_scheduler_integration(monkeypatch):
    with patch('database.metric_coll.find') as mock_find:
        mock_find.return_value = []
        sched = StrategyScheduler()
        with patch('allocation_engine.compute_weights', return_value={'lobby': 1.0}):
            sched.add('lobby', 'Lobbying', 'strategies.lobbying_growth', 'LobbyingGrowthStrategy', 'monthly')
            pf = sched.portfolios['lobby']
            pf.exec.order_to_pct = MagicMock(return_value=DummyOrder('AAPL'))
            pf.weights = {'AAPL': 1.0}
            inserted = {}
            monkeypatch.setattr('database.trade_coll.insert_one', lambda d: inserted.update(d))
            sched.portfolios['lobby'].rebalance()
            assert inserted['symbol'] == 'AAPL'
