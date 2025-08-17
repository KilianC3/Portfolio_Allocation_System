import math
from analytics import fundamentals as f

def test_compute_fundamental_metrics_handles_info_failure(monkeypatch):
    class FakeTicker:
        pass
    monkeypatch.setattr(f.yf, "Ticker", lambda s: FakeTicker())
    monkeypatch.setattr(f, "_fetch_info", lambda t: {})
    monkeypatch.setattr(f, "_piotroski", lambda t: 5.0)
    monkeypatch.setattr(f, "_altman", lambda t, info: 3.0)
    monkeypatch.setattr(f, "_roic", lambda t: 10.0)
    monkeypatch.setattr(f, "_fcf_yield", lambda t, info: 4.0)
    monkeypatch.setattr(f, "_beneish", lambda t: -1.0)
    metrics = f.compute_fundamental_metrics("AAPL")
    assert metrics["piotroski"] == 5.0
    assert math.isnan(metrics["short_ratio"])
    assert math.isnan(metrics["insider_buying"])
