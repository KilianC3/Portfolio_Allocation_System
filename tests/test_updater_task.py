import asyncio
import pandas as pd
import datetime as dt
import pytest

from tasks import updater


class DummyColl:
    def __init__(self):
        self.docs = {}

    def update_one(self, match, update, upsert=False):
        key = (match["portfolio_id"], match["date"])
        doc = self.docs.get(key, {})
        if "$set" in update:
            doc.update(update["$set"])
        else:
            doc.update(update)
        self.docs[key] = doc


@pytest.mark.asyncio
async def test_update_loop_stores_ret_and_exposure(monkeypatch):
    coll = DummyColl()
    monkeypatch.setattr(updater, "metric_coll", coll)
    messages: list[str] = []

    async def fake_broadcast(text: str):
        messages.append(text)

    monkeypatch.setattr(updater, "broadcast_message", fake_broadcast)

    returns = pd.Series([0.01], index=pd.to_datetime(["2024-01-01"]))
    exposure = pd.Series([0.5], index=pd.to_datetime(["2024-01-01"]))

    def fetch_returns():
        return {"pf1": (returns, exposure)}

    async def fake_sleep(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(updater.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await updater.update_loop(fetch_returns, interval=0)

    key = ("pf1", returns.index[0].date())
    assert coll.docs[key]["ret"] == 0.01
    assert coll.docs[key]["exposure"] == 0.5
    assert messages and "metrics" in messages[0]
