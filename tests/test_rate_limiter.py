import asyncio
import time
from infra.rate_limiter import AsyncRateLimiter


def test_rate_limiter_basic():
    rl = AsyncRateLimiter(2, 1)
    async def runner():
        async with rl:
            pass
        async with rl:
            pass
        t0 = time.perf_counter()
        await rl.acquire()
        t1 = time.perf_counter()
        assert t1 - t0 >= 1
    asyncio.run(runner())
