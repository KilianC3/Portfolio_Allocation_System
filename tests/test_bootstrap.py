import asyncio
import pytest


import scripts.bootstrap as boot
import scripts.health_check as hc
import scripts.populate as pop


@pytest.mark.asyncio
async def test_run_scrapers(monkeypatch):
    calls = []

    async def fake(*_a, **_k):
        calls.append("s")
        return [{"ok": 1}]

    monkeypatch.setattr(pop, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(pop, "download_sp500", lambda: calls.append("u"))
    monkeypatch.setattr(pop, "download_sp400", lambda: calls.append("u"))
    monkeypatch.setattr(pop, "download_russell2000", lambda: calls.append("u"))
    monkeypatch.setattr(pop, "load_sp500", lambda: ["AAPL"])
    monkeypatch.setattr(pop, "load_sp400", lambda: ["MSFT"])
    monkeypatch.setattr(pop, "load_russell2000", lambda: ["X"] * 2000)
    monkeypatch.setattr(pop, "fetch_politician_trades", fake)
    monkeypatch.setattr(pop, "fetch_lobbying_data", fake)
    monkeypatch.setattr(pop, "fetch_trending_wiki_views", fake)
    monkeypatch.setattr(pop, "fetch_dc_insider_scores", fake)
    monkeypatch.setattr(pop, "fetch_gov_contracts", fake)
    monkeypatch.setattr(pop, "fetch_app_reviews", fake)
    monkeypatch.setattr(pop, "fetch_google_trends", fake)
    monkeypatch.setattr(pop, "fetch_wsb_mentions", fake)
    monkeypatch.setattr(pop, "fetch_volatility_momentum_summary", fake)
    monkeypatch.setattr(pop, "fetch_leveraged_sector_summary", fake)
    monkeypatch.setattr(pop, "fetch_sector_momentum_summary", fake)
    monkeypatch.setattr(pop, "fetch_smallcap_momentum_summary", fake)
    monkeypatch.setattr(pop, "fetch_upgrade_momentum_summary", fake)
    monkeypatch.setattr(
        pop.full_fundamentals, "main", lambda *_a, **_k: calls.append("s")
    )
    monkeypatch.setattr(pop, "fetch_analyst_ratings", fake)
    monkeypatch.setattr(pop, "fetch_stock_news", fake)
    monkeypatch.setattr(pop, "fetch_insider_buying", fake)
    monkeypatch.setattr(
        pop,
        "fetch_sp500_history",
        lambda d: calls.append("s")
        or [{"open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
    )
    monkeypatch.setattr(pop, "update_all_ticker_scores", lambda: calls.append("s"))

    await pop.run_scrapers()
    assert calls.count("s") == 19


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
    import service.start as start_mod

    monkeypatch.setattr(start_mod, "db_ping", lambda: True)

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

    monkeypatch.setattr(start_mod, "AlpacaGateway", lambda: DummyGW())
    monkeypatch.setattr(start_mod, "MasterLedger", DummyLedger)
    await start_mod.system_checklist()


def test_bootstrap_main(monkeypatch):
    calls = []

    async def fake_main():
        calls.append("api")

    monkeypatch.setattr(boot, "start_main", fake_main)

    boot.main()
    assert calls == ["api"]


@pytest.mark.asyncio
async def test_startup_runs_without_scrapers(monkeypatch):
    import service.start as start_mod
    import service.api as api_mod
    from scripts import populate as pop_mod

    calls: list[str] = []

    async def fake_launch_server(*_a, **_k):
        calls.append("api")
        await api_mod.startup_event()
        return asyncio.create_task(asyncio.sleep(0.01))

    monkeypatch.setattr(start_mod, "_launch_server", fake_launch_server)
    monkeypatch.setattr(start_mod, "validate_config", lambda: calls.append("cfg"))

    async def fake_checklist():
        calls.append("chk")

    monkeypatch.setattr(start_mod, "system_checklist", fake_checklist)
    monkeypatch.setattr(start_mod, "init_db", lambda: calls.append("db"))
    monkeypatch.setattr(start_mod, "load_portfolios", lambda: calls.append("load"))

    # avoid real HTTP requests during API connectivity check
    class DummyResponse:
        def raise_for_status(self):
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_a, **_k):
            return DummyResponse()

    monkeypatch.setattr(start_mod.httpx, "AsyncClient", lambda: DummyClient())

    called: list[str] = []

    async def fake_run_scrapers(force=True):
        called.append("scrapers")

    monkeypatch.setattr(pop_mod, "run_scrapers", fake_run_scrapers)
    monkeypatch.setattr(api_mod.sched, "register_jobs", lambda: None)
    monkeypatch.setattr(api_mod, "AUTO_START_SCHED", False)

    await start_mod.main("x", 0)
    await asyncio.sleep(0)
    assert "api" in calls
    assert called == []
