import asyncio
from unittest import mock
import pandas as pd
import pytest

import scrapers.dc_insider as dc
import scrapers.lobbying as lb
import scrapers.gov_contracts as gc
import scrapers.politician as pol
import scrapers.wiki as wiki
import scrapers.analyst_ratings as ar
import scrapers.universe as univ
import scrapers.sp500_index as spx
import scrapers.google_trends as gt


async def _fake_get(*_args, **_kw):
    return """
    <table>
        <tr><th>Ticker</th><th>Val1</th><th>Date</th></tr>
        <tr><td>AAPL</td><td>1</td><td>2024-01-01</td></tr>
    </table>
    """


async def _fake_get_lobby(*_args, **_kw):
    return """
    <table>
        <tr><th>Ticker</th><th>Client</th><th>Amount</th><th>Date</th></tr>
        <tr><td>AAPL</td><td>X</td><td>$1</td><td>2024-01-01</td></tr>
    </table>
    """


async def _fake_get_politician(*_args, **_kw):
    return """
    <table>
        <tr><th>Politician</th><th>Ticker</th><th>Type</th><th>Amount</th><th>Date</th></tr>
        <tr><td>Rep</td><td>AAPL</td><td>buy</td><td>1</td><td>2024-01-01</td></tr>
    </table>
    """


async def _fake_get_wiki(*_args, **_kw):
    return '{"items": [{"timestamp": "2024010100", "views": 42}]}'


@mock.patch.object(dc, "scrape_get", side_effect=_fake_get)
@mock.patch.object(gc, "scrape_get", side_effect=_fake_get)
@mock.patch.object(pol, "scrape_get", side_effect=_fake_get_politician)
@mock.patch.object(wiki, "scrape_get", side_effect=_fake_get_wiki)
@mock.patch.object(gt, "scrape_get", side_effect=_fake_get)
@mock.patch.object(lb, "scrape_get", side_effect=_fake_get_lobby)
@mock.patch.object(dc, "insider_coll", new=mock.Mock())
@mock.patch.object(lb, "lobby_coll", new=mock.Mock())
@mock.patch.object(gc, "contracts_coll", new=mock.Mock())
@mock.patch.object(pol, "politician_coll", new=mock.Mock())
@mock.patch.object(wiki, "wiki_collection", new=mock.Mock())
@mock.patch.object(
    spx.yf,
    "download",
    return_value=pd.DataFrame(
        {
            "Open": [4950],
            "High": [5050],
            "Low": [4900],
            "Close": [5000],
            "Volume": [1000000],
        },
        index=pd.to_datetime(["2024-01-01"]),
    ),
)
@mock.patch.object(spx, "sp500_coll", new=mock.Mock())
@pytest.mark.asyncio
async def test_scraper_suite(
    _dl,
    _lb_get,
    _gt_get,
    _wiki_get,
    _pol_get,
    _gc_get,
    _dc_get,
    monkeypatch,
):
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
                                    "<table>"
                                    "<tr><th>Ticker</th><th>Client</th><th>Amount</th><th>Date</th></tr>"
                                    "<tr><td>AAPL</td><td>X</td><td>1</td><td>2024-01-01</td></tr>"
                                    "</table>"
                                )

                        return P()

                    async def close(self):
                        pass

                return B()

    monkeypatch.setattr(lb, "async_playwright", lambda: DummyPW())
    d = await dc.fetch_dc_insider_scores()
    l = await lb.fetch_lobbying_data()
    g = await gc.fetch_gov_contracts()
    p = await pol.fetch_politician_trades()
    w = await wiki.fetch_wiki_views()
    index = spx.fetch_sp500_history(1)
    assert d and l and g and p and w and index
    assert "open" in index[0]


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
