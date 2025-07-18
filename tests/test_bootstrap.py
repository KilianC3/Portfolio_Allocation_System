import pytest


import scripts.bootstrap as boot
import scripts.health_check as hc


@pytest.mark.asyncio
async def test_run_scrapers(monkeypatch):
    calls = []

    async def fake(*_a, **_k):
        calls.append("s")
        return [{"ok": 1}]

    monkeypatch.setattr(boot, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(boot, "download_sp500", lambda: calls.append("u"))
    monkeypatch.setattr(boot, "download_sp400", lambda: calls.append("u"))
    monkeypatch.setattr(boot, "download_russell2000", lambda: calls.append("u"))
    monkeypatch.setattr(boot, "load_sp500", lambda: ["AAPL"])
    monkeypatch.setattr(boot, "load_sp400", lambda: ["MSFT"])
    monkeypatch.setattr(boot, "load_russell2000", lambda: ["X"] * 2000)
    monkeypatch.setattr(boot, "fetch_politician_trades", fake)
    monkeypatch.setattr(boot, "fetch_lobbying_data", fake)
    monkeypatch.setattr(boot, "fetch_trending_wiki_views", fake)
    monkeypatch.setattr(boot, "fetch_dc_insider_scores", fake)
    monkeypatch.setattr(boot, "fetch_gov_contracts", fake)
    monkeypatch.setattr(boot, "fetch_app_reviews", fake)
    monkeypatch.setattr(boot, "fetch_google_trends", fake)
    monkeypatch.setattr(boot, "fetch_wsb_mentions", fake)
    monkeypatch.setattr(boot, "fetch_analyst_ratings", fake)
    monkeypatch.setattr(boot, "fetch_stock_news", fake)
    monkeypatch.setattr(boot, "fetch_insider_buying", fake)
    monkeypatch.setattr(boot, "fetch_sp500_history", lambda d: [{"close": 1}])
    monkeypatch.setattr(boot, "update_all_ticker_scores", lambda: calls.append("s"))

    await boot.run_scrapers()
    assert calls.count("s") == 12


def test_health(monkeypatch):
    monkeypatch.setattr(
        hc.db, "client", type("C", (), {"command": lambda self, c: None})()
    )
    monkeypatch.setattr(hc.pf_coll, "find", lambda *a, **k: [1])
    monkeypatch.setattr(hc.trade_coll, "find", lambda *a, **k: [1, 2])
    monkeypatch.setattr(hc.metric_coll, "find", lambda *a, **k: [{"date": "x"}])
    monkeypatch.setattr(hc, "load_sp500", lambda: ["AAPL"])
    monkeypatch.setattr(hc, "load_sp400", lambda: ["MSFT"])
    monkeypatch.setattr(hc, "load_russell2000", lambda: [])
    out = hc.check_system()
    assert out["database"] == "ok"
    assert out["tracked_universe"] == 2


@pytest.mark.asyncio
async def test_system_checklist(monkeypatch):
    monkeypatch.setattr(boot, "db_ping", lambda: True)

    class DummyGW:
        async def account(self):
            return {"id": 1}

        async def close(self):
            pass

    class DummyLedger:
        def __init__(self) -> None:
            class R:
                async def ping(self):
                    pass

            self.redis = R()

    monkeypatch.setattr(boot, "AlpacaGateway", lambda: DummyGW())
    monkeypatch.setattr(boot, "MasterLedger", DummyLedger)
    await boot.system_checklist()
