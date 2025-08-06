"""Tests for MasterLedger reservation cancellation."""

import pytest

from ledger.master_ledger import MasterLedger


class DummyRedis:
    def __init__(self):
        self.streams: dict[str, list[dict]] = {}

    async def xadd(self, key, data):
        self.streams.setdefault(key, []).append(data)
        return "id"

    async def xrange(self, key):
        return [(str(i), d) for i, d in enumerate(self.streams.get(key, []))]

    async def xtrim(self, key, maxlen, approximate=True):
        if key in self.streams and len(self.streams[key]) > maxlen:
            self.streams[key] = self.streams[key][-maxlen:]


@pytest.mark.asyncio
async def test_cancel_restores_free_float(monkeypatch):
    ledger = MasterLedger()
    dummy = DummyRedis()
    monkeypatch.setattr(ledger, "redis", dummy)

    key = await ledger.reserve("pf1", "AAPL", 10)
    assert await ledger.free_float("pf1", "AAPL") == pytest.approx(-10)

    await ledger.cancel(key, 10)
    assert await ledger.free_float("pf1", "AAPL") == pytest.approx(0)
