import asyncio
from unittest import mock
import pandas as pd
import pytest
from typing import Any

import scrapers.analyst_ratings as ar
import scrapers.universe as univ
import scrapers.volatility_momentum as vm
import scrapers.google_trends as gt
import scrapers.lobbying as lb
import scrapers.sector_momentum as sm
import scrapers.leveraged_sector_momentum as lsm
import scrapers.smallcap_momentum as scm
import scrapers.upgrade_momentum as um
from scrapers.yf_utils import flatten_columns


async def _fake_get(*_args, **_kw):
    return """
    <table>
        <tr><th>Ticker</th><th>Val1</th><th>Date</th></tr>
        <tr><td>AAPL</td><td>1</td><td>2024-01-01</td></tr>
    </table>
    """


@mock.patch.object(ar, "fetch_upgrades")
@mock.patch.object(ar, "init_db")
@pytest.mark.asyncio
async def test_fetch_analyst_ratings_formats_rows(mock_init_db, mock_fetch_upgrades):
    df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01", tz="UTC"),
                "ticker": "AAPL",
                "company_name": "Apple",
                "analyst": "Jane",
                "rating_current": "Buy",
                "pt_prior": 100.0,
                "pt_current": 110.0,
                "pt_pct_change": 10.0,
                "importance": 5,
                "notes": "note",
                "action": "UPGRADE",
            }
        ]
    )
    mock_fetch_upgrades.return_value = (df, df)
    rows = await ar.fetch_analyst_ratings(limit=1)
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["date_utc"] == "2024-01-01T00:00:00+00:00"


def test_helpers(monkeypatch, tmp_path):
    data = [{"date_utc": "2024-01-01T00:00:00Z", "ticker": "AAPL", "action": "UPGRADE"}]

    async def fake_fetch(limit=200):
        return data

    monkeypatch.setattr(ar, "fetch_analyst_ratings", fake_fetch)
    out = asyncio.run(ar.fetch_changes(["AAPL"], weeks=4))
    assert not out.empty and out.iloc[0]["symbol"] == "AAPL"
    print(out.iloc[0])

    csv_text = "symbol\nAAPL\n"

    class Resp:
        text = csv_text

        def raise_for_status(self):
            pass

    monkeypatch.setattr(univ, "_tickers_from_wiki", lambda url: ["MSFT"])
    monkeypatch.setattr(univ.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(univ, "universe_coll", mock.Mock())
    monkeypatch.setattr(univ, "universe_coll", mock.Mock())
    p = univ.download_sp500(tmp_path / "sp.csv")
    assert p.exists()
    data = pd.read_csv(p)
    assert data.iloc[0][0] == "AAPL"
    print(data.iloc[0].to_dict())

    p400 = univ.download_sp400(tmp_path / "sp400.csv")
    assert p400.exists()
    data400 = pd.read_csv(p400)
    assert data400.iloc[0][0] == "MSFT"

    monkeypatch.setattr(univ.requests, "get", lambda *a, **k: Resp())
    p2 = univ.download_russell2000(tmp_path / "r2k.csv")
    assert p2.exists()
    data2 = pd.read_csv(p2)
    assert data2.iloc[0][0] == "MSFT"
    print(data2.iloc[0].to_dict())


@mock.patch.object(vm, "append_snapshot")
@mock.patch.object(vm, "vol_mom_coll", new=mock.Mock())
@mock.patch.object(vm, "load_universe_any")
@mock.patch.object(vm, "_weekly_closes")
def test_volatility_momentum_returns_metrics(mock_weekly, mock_universe, *_):
    mock_universe.return_value = pd.DataFrame({"ticker": ["AAPL", "MSFT"]})

    def fake_weekly(tickers, weeks):
        dates = pd.date_range("2024-01-01", periods=weeks + 1, freq="W")
        data = {t: range(1, weeks + 2) for t in tickers}
        return pd.DataFrame(data, index=dates)

    mock_weekly.side_effect = fake_weekly
    rows = vm.fetch_volatility_momentum_summary(weeks=12, top_n=1, max_tickers=2)
    assert "score" in rows[0] and "ret_52w" in rows[0]


@pytest.mark.asyncio
async def test_google_trends_json(monkeypatch):
    monkeypatch.setattr(gt, "trends_coll", mock.Mock())
    monkeypatch.setattr(gt, "scrape_get", _fake_get)

    class DummyPW:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        class chromium:
            @staticmethod
            async def launch(headless=True):
                class B:
                    async def new_page(self):
                        class P:
                            async def goto(self, _):
                                pass

                            async def content(self):
                                return (
                                    "<table><tr><th>Ticker</th><th>Val1</th><th>Date"
                                    "</th></tr><tr><td>AAPL</td><td>1</td><td>2024-01-01"
                                    "</td></tr></table>"
                                )

                        return P()

                    async def close(self):
                        pass

                return B()

    class DummyRate:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr(gt, "async_playwright", lambda: DummyPW())
    monkeypatch.setattr(gt, "rate", DummyRate())
    rows = await gt.fetch_google_trends()
    assert rows and rows[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_lobbying_no_table(monkeypatch):
    monkeypatch.setattr(lb, "lobby_coll", mock.Mock())
    monkeypatch.setattr(lb, "scrape_get", lambda *_a, **_k: "<html></html>")

    class DummyPW:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        class chromium:
            @staticmethod
            async def launch(headless=True):
                class B:
                    async def new_page(self):
                        class P:
                            async def goto(self, _):
                                pass

                            async def content(self):
                                return "<html></html>"

                        return P()

                    async def close(self):
                        pass

                return B()

    class DummyRate:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr(lb, "rate", DummyRate())
    monkeypatch.setattr(lb, "async_playwright", lambda: DummyPW())
    rows = await lb.fetch_lobbying_data()
    assert rows == []


def _fake_weekly_closes(tickers, weeks):
    idx = pd.date_range("2024-01-01", periods=weeks + 1, freq="W")
    data = {sym: range(1, weeks + 2) for sym in tickers}
    return pd.DataFrame(data, index=idx)


@pytest.mark.asyncio
async def test_momentum_scrapers(monkeypatch):
    tickers = [f"T{i}" for i in range(6)]

    monkeypatch.setattr(sm, "_weekly_closes", _fake_weekly_closes)
    monkeypatch.setattr(sm, "sector_mom_coll", mock.Mock())
    rows = sm.fetch_sector_momentum_summary(weeks=1, top_n=5)
    assert len(rows) == 5

    monkeypatch.setattr(lsm, "_weekly_closes", _fake_weekly_closes)
    monkeypatch.setattr(lsm, "lev_sector_coll", mock.Mock())
    rows = lsm.fetch_leveraged_sector_summary(weeks=1, top_n=5)
    assert len(rows) == 5

    monkeypatch.setattr(scm, "_weekly_closes", _fake_weekly_closes)
    monkeypatch.setattr(scm, "smallcap_mom_coll", mock.Mock())
    rows = scm.fetch_smallcap_momentum_summary(tickers, weeks=1, top_n=5, max_tickers=5)
    assert len(rows) == 5

    async def fake_changes(symbols, weeks=4):
        return pd.DataFrame(
            {
                "symbol": symbols,
                "upgrades": [1] * len(symbols),
                "downgrades": [0] * len(symbols),
                "total": [1] * len(symbols),
            }
        )

    monkeypatch.setattr(um, "fetch_changes", fake_changes)
    monkeypatch.setattr(um, "upgrade_mom_coll", mock.Mock())
    rows = await um.fetch_upgrade_momentum_summary(tickers, weeks=1, top_n=5)
    assert len(rows) == 5

    monkeypatch.setattr(vm, "_weekly_closes", _fake_weekly_closes)
    monkeypatch.setattr(vm, "vol_mom_coll", mock.Mock())
    monkeypatch.setattr(
        vm, "load_universe_any", lambda: pd.DataFrame({"ticker": tickers})
    )
    rows = vm.fetch_volatility_momentum_summary(weeks=2, top_n=5, max_tickers=5)
    assert len(rows) == 5


def test_weekly_closes_uses_explicit_dates(monkeypatch):
    import scrapers.momentum_common as mc

    called: dict[str, Any] = {}

    def fake_download(
        tickers, start, end, interval, group_by, threads, progress, auto_adjust, actions
    ):
        called.update(
            {
                "start": start,
                "end": end,
                "auto_adjust": auto_adjust,
                "actions": actions,
            }
        )
        idx = pd.date_range(start, periods=3, freq="W")
        cols = pd.MultiIndex.from_product([["Close"], tickers])
        data = [[1] * len(tickers) for _ in range(3)]
        return pd.DataFrame(data, index=idx, columns=cols)

    monkeypatch.setattr(mc.yf, "download", fake_download)
    df = mc._weekly_closes(["A", "B"], weeks=2)
    assert called["auto_adjust"] is False
    assert called["actions"] is False
    assert df.columns.tolist() == ["A", "B"]
    assert len(df) == 3


def test_flatten_columns_multiindex():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    cols = pd.MultiIndex.from_product([["AAPL", "MSFT"], ["Close", "Volume"]])
    data = [[1, 2, 3, 4], [5, 6, 7, 8]]
    df = pd.DataFrame(data, index=idx, columns=cols)
    flat = flatten_columns(df)
    assert flat.columns.tolist() == [
        "AAPL_Close",
        "AAPL_Volume",
        "MSFT_Close",
        "MSFT_Volume",
    ]
