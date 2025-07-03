import os
os.environ["TESTING"] = "1"
import asyncio
import api
from scrapers import politician, lobbying, wiki, dc_insider, gov_contracts

async def fake_get(url):
    if "politician" in url:
        return """
        <table>
          <tr><th>Name</th><th>Ticker</th><th>Type</th><th>Amount</th><th>Date</th></tr>
          <tr><td>John Doe</td><td>AAPL</td><td>Purchase</td><td>$10,000</td><td>2024-01-01</td></tr>
        </table>
        """
    if "lobbying" in url:
        return """
        <table>
          <tr><th>Ticker</th><th>Client</th><th>Amount</th><th>Date</th></tr>
          <tr><td>AAPL</td><td>Firm</td><td>$5,000</td><td>2024-01-01</td></tr>
        </table>
        """
    if "governmentcontracts" in url:
        return """
        <table>
          <tr><th>Ticker</th><th>Value</th><th>Date</th></tr>
          <tr><td>AAPL</td><td>$20,000</td><td>2024-01-01</td></tr>
        </table>
        """
    if "dcinsiderscore" in url:
        return """
        <table>
          <tr><th>Ticker</th><th>Score</th><th>Date</th></tr>
          <tr><td>AAPL</td><td>75</td><td>2024-01-01</td></tr>
        </table>
        """
    return """
        <table>
          <tr><th>Ticker</th><th>Views</th><th>Date</th></tr>
          <tr><td>AAPL</td><td>1000</td><td>2024-01-01</td></tr>
        </table>
        """

def test_fetch_politician_scrape(monkeypatch):
    monkeypatch.setattr(politician, "scrape_get", fake_get)
    inserted = {}
    monkeypatch.setattr(api.politician_coll, "update_one", lambda q,u,upsert=None: inserted.update(u["$set"]))
    data = asyncio.run(api.fetch_politician_trades())
    assert len(data) == 1
    assert inserted["ticker"] == "AAPL"


def test_fetch_lobbying_scrape(monkeypatch):
    monkeypatch.setattr(lobbying, "scrape_get", fake_get)
    inserted = {}
    monkeypatch.setattr(api.lobby_coll, "update_one", lambda q,u,upsert=None: inserted.update(u["$set"]))
    data = asyncio.run(api.fetch_lobbying_data())
    assert len(data) == 1
    assert "client" in inserted


def test_fetch_wiki_views_scrape(monkeypatch):
    monkeypatch.setattr(wiki, "scrape_get", fake_get)
    inserted = {}
    monkeypatch.setattr(api.wiki_collection, "update_one", lambda q,u,upsert=None: inserted.update(u["$set"]))
    data = asyncio.run(api.fetch_wiki_views())
    assert len(data) == 1
    assert inserted["ticker"] == "AAPL"


def test_fetch_dc_insider_scrape(monkeypatch):
    monkeypatch.setattr(dc_insider, "scrape_get", fake_get)
    inserted = {}
    monkeypatch.setattr(api.insider_coll, "update_one", lambda q,u,upsert=None: inserted.update(u["$set"]))
    data = asyncio.run(api.fetch_dc_insider_scores())
    assert len(data) == 1
    assert inserted["score"] == "75"


def test_fetch_gov_contracts_scrape(monkeypatch):
    monkeypatch.setattr(gov_contracts, "scrape_get", fake_get)
    inserted = {}
    monkeypatch.setattr(api.contracts_coll, "update_one", lambda q,u,upsert=None: inserted.update(u["$set"]))
    data = asyncio.run(api.fetch_gov_contracts())
    assert len(data) == 1
    assert inserted["value"] == "$20,000"

