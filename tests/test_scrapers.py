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
        <tr><td>AAPL</td><td>X</td><td>1</td><td>2024-01-01</td></tr>
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
@mock.patch.object(lb, "scrape_get", side_effect=_fake_get_lobby)
@mock.patch.object(gc, "scrape_get", side_effect=_fake_get)
@mock.patch.object(pol, "scrape_get", side_effect=_fake_get_politician)
@mock.patch.object(wiki, "scrape_get", side_effect=_fake_get_wiki)
@mock.patch.object(dc, "insider_coll", new=mock.Mock())
@mock.patch.object(lb, "lobby_coll", new=mock.Mock())
@mock.patch.object(gc, "contracts_coll", new=mock.Mock())
@mock.patch.object(pol, "politician_coll", new=mock.Mock())
@mock.patch.object(wiki, "wiki_collection", new=mock.Mock())
@mock.patch.object(
    spx.yf,
    "download",
    return_value=pd.DataFrame({"Close": [5000]}, index=pd.to_datetime(["2024-01-01"])),
)
@mock.patch.object(spx, "sp500_coll", new=mock.Mock())
@pytest.mark.asyncio
async def test_scraper_suite(
    _dl,
    _mw,
    _mp,
    _mg,
    _ml,
    _md,
):
    d = await dc.fetch_dc_insider_scores()
    l = await lb.fetch_lobbying_data()
    g = await gc.fetch_gov_contracts()
    p = await pol.fetch_politician_trades()
    w = await wiki.fetch_wiki_views()
    index = spx.fetch_sp500_history(1)
    assert d and l and g and p and w and index
    print(index[0])


def test_helpers(monkeypatch, tmp_path):
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "rating": ["upgrade"]})

    async def fake_fetch(sym):
        return df

    monkeypatch.setattr(ar, "_fetch_ticker", fake_fetch)
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
    p = univ.download_sp1500(tmp_path / "sp.csv")
    assert p.exists()
    data = pd.read_csv(p)
    assert data.iloc[0][0] == "AAPL"
    print(data.iloc[0].to_dict())

    monkeypatch.setattr(univ.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(univ, "universe_coll", mock.Mock())
    p2 = univ.download_russell2000(tmp_path / "r2k.csv")
    assert p2.exists()
    data2 = pd.read_csv(p2)
    assert data2.iloc[0][0] == "AAPL"
    print(data2.iloc[0].to_dict())
