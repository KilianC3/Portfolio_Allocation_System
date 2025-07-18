import datetime as dt
import hashlib
import pytest

from infra import smart_scraper
from database import InMemoryCollection


@pytest.mark.asyncio
async def test_get_handles_naive_expire(monkeypatch):
    url = 'http://example.com'
    key = hashlib.md5(url.encode()).hexdigest()
    mem = InMemoryCollection()
    mem.replace_one({'key': key}, {'key': key, 'payload': 'cached', 'expire': dt.datetime.now() + dt.timedelta(seconds=60)}, upsert=True)
    monkeypatch.setattr(smart_scraper, 'cache', mem)
    monkeypatch.setattr(smart_scraper.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))

    result = await smart_scraper.get(url)
    assert result == 'cached'
