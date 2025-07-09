import asyncio
from collections import deque


class AsyncRateLimiter:
    """Async token bucket with fairness."""

    def __init__(self, max_calls: int, period: float) -> None:
        self.max_calls = max_calls
        self.period = period
        self.calls: deque[float] = deque()
        self.cond = asyncio.Condition()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, _exc_type, _exc, _val) -> None:
        pass

    async def acquire(self) -> None:
        async with self.cond:
            loop = asyncio.get_event_loop()
            while True:
                now = loop.time()
                while self.calls and self.calls[0] <= now - self.period:
                    self.calls.popleft()
                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    self.cond.notify_all()
                    return
                await self.cond.wait()


class DynamicRateLimiter(AsyncRateLimiter):
    """Rate limiter that expands the waiting period when backoff is triggered."""

    def __init__(
        self,
        max_calls: int,
        period: float,
        factor: float = 2.0,
        max_period: float = 60.0,
    ) -> None:
        super().__init__(max_calls, period)
        self.base_period = period
        self.factor = factor
        self.max_period = max_period

    def backoff(self) -> None:
        """Increase the period exponentially up to ``max_period``."""
        self.period = min(self.period * self.factor, self.max_period)

    def reset(self) -> None:
        """Reset the period to the original value."""
        self.period = self.base_period
