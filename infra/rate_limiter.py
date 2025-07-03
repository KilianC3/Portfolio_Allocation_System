import asyncio, time
class AsyncRateLimiter:
    def __init__(self,max_calls:int,period:float):
        self.max_calls=max_calls; self.period=period
        self.calls=[]; self.lock=asyncio.Lock()
    async def __aenter__(self):
        await self.acquire(); return self
    async def __aexit__(self, _exc_type, _exc, _val):
        pass
    async def acquire(self):
        while True:
            async with self.lock:
                now=time.time()
                self.calls=[t for t in self.calls if t>now-self.period]
                if len(self.calls)<self.max_calls:
                    self.calls.append(now); return
            await asyncio.sleep(0.25)
