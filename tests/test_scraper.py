import os

os.environ["PG_URI"] = "postgresql://localhost/test"

import pytest

aiohttp = pytest.importorskip("aiohttp")
aioresponses = pytest.importorskip("aioresponses")

from infra.smart_scraper import get


@pytest.mark.asyncio
async def test_scraper_caching():
    url = "http://example.com"
    with aioresponses() as m:
        m.get(url, status=200, body="hello")
        text1 = await get(url)
        assert text1 == "hello"
        # subsequent call should hit cache even if server fails
        m.get(url, status=500)
        text2 = await get(url)
        assert text2 == "hello"
