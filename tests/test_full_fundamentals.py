from scrapers import full_fundamentals as ff


class DummyTicker:
    def __init__(self, *_, **__):
        pass

    def get_info(self):
        raise ff.HTTPError("401")

    @property
    def fast_info(self):
        raise Exception("fail")


def test_fetch_fundamentals_edgar_fallback(monkeypatch):
    monkeypatch.setattr(ff.yf, "Ticker", lambda *a, **k: DummyTicker())
    monkeypatch.setattr(ff, "fetch_edgar_facts", lambda s: {"sharesOutstanding": 99})
    monkeypatch.setattr(ff.time, "sleep", lambda *_: None)
    data = ff.fetch_fundamentals("ABC")
    assert data == {"sharesOutstanding": 99}
