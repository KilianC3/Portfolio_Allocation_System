from service import cache


def test_cache_hit_and_invalidation(monkeypatch):
    cache.clear()
    now = 1000.0
    monkeypatch.setattr(cache.time, "time", lambda: now)
    cache.set("a", 1, ttl=1)
    assert cache.get("a") == 1
    # expire
    monkeypatch.setattr(cache.time, "time", lambda: now + 2)
    assert cache.get("a") is None

    # prefix invalidation
    monkeypatch.setattr(cache.time, "time", lambda: now)
    cache.set("p:1", 1, ttl=10)
    cache.set("p:2", 2, ttl=10)
    cache.invalidate_prefix("p:")
    assert cache.get("p:1") is None
    assert cache.get("p:2") is None
