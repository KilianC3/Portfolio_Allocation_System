import time
from risk.circuit import CircuitBreaker


def test_circuit_breaker():
    cb = CircuitBreaker(cooldown_minutes=1)
    assert not cb.tripped
    cb.trip()
    assert cb.tripped
    cb.reset()
    assert not cb.tripped
