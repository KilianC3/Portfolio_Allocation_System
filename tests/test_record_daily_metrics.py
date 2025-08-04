import pandas as pd

from analytics import utils


def test_record_daily_metrics(monkeypatch):
    series = pd.Series([0.01, -0.02], index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    weights = {"AAA": 0.6, "BBB": 0.4}

    returns_docs = []
    metrics_docs = []

    class DummyReturns:
        conn = True

        def update_one(self, match, update, upsert=False):
            doc = {**match, **update["$set"]}
            returns_docs.append(doc)

    class DummyMetrics:
        def update_one(self, match, update, upsert=False):
            doc = {**match, **update["$set"]}
            metrics_docs.append(doc)

    monkeypatch.setattr(utils, "returns_coll", DummyReturns())
    monkeypatch.setattr(utils, "metric_coll", DummyMetrics())
    monkeypatch.setattr(utils, "ticker_sector", lambda sym: "Tech" if sym == "AAA" else "Finance")

    utils.record_daily_metrics("pf1", series, weights)

    assert len(returns_docs) == 2
    assert any(d["return_pct"] == -0.02 for d in returns_docs)
    assert metrics_docs[0]["exposures"]["Tech"] == 0.6
    assert metrics_docs[0]["exposures"]["Finance"] == 0.4
