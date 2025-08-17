import asyncio
import pandas as pd
import datetime as dt
import pytest

from tasks import updater
import analytics.performance_tracking as perf


class DummyColl:
    def __init__(self):
        self.docs = {}

    def insert_many(self, docs):
        for doc in docs:
            key = (doc["portfolio_id"], doc["date"])
            self.docs[key] = doc

    def update_one(self, match, update, upsert=False):
        key = (match["portfolio_id"], match["date"])
        doc = self.docs.get(key, {})
        doc.update(update.get("$set", update))
        self.docs[key] = doc


class PerfColl:
    def __init__(self):
        self.docs = []

    def update_one(self, match, update, upsert=False):
        doc = match.copy()
        doc.update(update.get("$set", {}))
        self.docs.append(doc)


@pytest.mark.asyncio
async def test_update_loop_stores_ret_and_exposure(monkeypatch):
    coll = DummyColl()
    perf_coll = PerfColl()
    monkeypatch.setattr(updater, "metric_coll", coll)
    monkeypatch.setattr(perf, "alloc_perf_coll", perf_coll)
    captured: dict[str, list[str]] = {}

    original_track = updater.track_allocation_performance

    def capture_track(df):
        captured["cols"] = list(df.columns)
        return original_track(df)

    monkeypatch.setattr(updater, "track_allocation_performance", capture_track)
    messages: list[str] = []

    async def fake_broadcast(text: str):
        messages.append(text)

    monkeypatch.setattr(updater, "broadcast_message", fake_broadcast)

    returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))
    exposure = pd.Series([0.5], index=pd.to_datetime(["2024-01-01"]))
    asset = pd.DataFrame({"A": [0.02], "B": [-0.01]}, index=returns.index)

    def fetch_returns():
        return {"pf1": (returns, exposure, asset)}

    async def fake_sleep(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(updater.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await updater.update_loop(fetch_returns, interval=0)

    key = ("pf1", returns.index[0].date())
    assert coll.docs[key]["ret"] == 0.01
    assert coll.docs[key]["exposure"] == 0.5
    assert messages and "metrics" in messages[0]
    methods = {d["method"] for d in perf_coll.docs}
    assert "max_sharpe" in methods
    assert len(perf_coll.docs) >= 5
    assert captured.get("cols") == ["A", "B"]
