"""Tests for EquityPortfolio weight normalisation and PnL tracking."""

from types import SimpleNamespace

import pytest

from core import equity as equity_mod
from analytics import utils as util_mod


class DummyColl:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)

    def find(self, q=None):
        q = q or {}
        def match(d):
            return all(d.get(k) == v for k, v in q.items())
        return [d for d in self.docs if match(d)]

    def find_one(self, q):
        for d in self.find(q):
            return d
        return None

    def update_one(self, match, update, upsert=False):
        doc = self.find_one(match)
        if doc:
            doc.update(update.get("$set", {}))
        elif upsert:
            new_doc = match.copy()
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)


class DummyGW:
    symbols = ["AAPL", "MSFT"]


def setup_portfolio(monkeypatch):
    pf_coll = DummyColl()
    weight_coll = DummyColl()
    trade_coll = DummyColl()
    pos_coll = DummyColl()

    monkeypatch.setattr(equity_mod, "pf_coll", pf_coll)
    monkeypatch.setattr(equity_mod, "weight_coll", weight_coll)
    monkeypatch.setattr(equity_mod, "trade_coll", trade_coll)
    monkeypatch.setattr(equity_mod, "position_coll", pos_coll)
    monkeypatch.setattr(util_mod, "position_coll", pos_coll)

    pf = equity_mod.EquityPortfolio("test", gateway=DummyGW(), pf_id="pf1")
    return pf, pf_coll, weight_coll, trade_coll, pos_coll


def test_set_weights_normalises_and_cash(monkeypatch):
    pf, pf_coll, weight_coll, *_ = setup_portfolio(monkeypatch)
    pf.set_weights({"AAPL": 0.4, "MSFT": 0.4})
    assert pf.weights == {"AAPL": 0.4, "MSFT": 0.4}
    saved = pf_coll.docs[0]["weights"]
    assert pytest.approx(sum(saved.values())) == 1.0
    assert saved["cash"] == pytest.approx(0.2)


def test_set_weights_unknown_symbol(monkeypatch):
    pf, *_ = setup_portfolio(monkeypatch)
    with pytest.raises(ValueError):
        pf.set_weights({"AAPL": 0.5, "GOOG": 0.5})


def test_trade_logging_and_pnl(monkeypatch):
    pf, _, _, trade_coll, pos_coll = setup_portfolio(monkeypatch)
    buy = SimpleNamespace(symbol="AAPL", side="buy", qty=10, filled_avg_price=100)
    sell = SimpleNamespace(symbol="AAPL", side="sell", qty=5, filled_avg_price=110)
    pf._log_trade(buy)
    pf._log_trade(sell)

    pos = pos_coll.find_one({"portfolio_id": pf.id, "symbol": "AAPL"})
    assert pos["qty"] == 5
    assert pos["cost_basis"] == pytest.approx(500)
    assert pos["realized_pnl"] == pytest.approx(50)

    assert pf.positions() == {"AAPL": 5}

    prices = {"AAPL": 120}
    pnl = util_mod.unrealized_pnl(pf.id, prices)
    assert pnl["AAPL"] == pytest.approx(100)
    assert pnl["total"] == pytest.approx(100)

    # trade history still matches aggregated position
    manual = 0
    for d in trade_coll.docs:
        q = d["qty"]
        if d["side"] == "sell":
            q *= -1
        manual += q
    assert manual == 5
