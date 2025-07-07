import asyncio
import time

import pytest

from infra.rate_limiter import DynamicRateLimiter


def test_dynamic_rate_limiter_backoff():
    rate = DynamicRateLimiter(1, 0.1, factor=2.0, max_period=1.0)
    rate.backoff()
    assert rate.period > 0.1
    rate.reset()
    assert rate.period == 0.1
