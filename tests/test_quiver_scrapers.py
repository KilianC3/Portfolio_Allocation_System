import asyncio
from unittest import mock

import pytest

import scrapers.app_reviews as app
import scrapers.dc_insider as dc
import scrapers.insider_buying as ins
import scrapers.politician as pol
import scrapers.gov_contracts as gc
from scrapers.utils import validate_row


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,coll,func_name,html,expected",
    [
        (
            app,
            "app_reviews_coll",
            "fetch_app_reviews",
            """
            <table>
              <tr><th>Company</th><th>Date</th><th>Hype</th><th>Ticker</th></tr>
              <tr><td>Apple</td><td>2024-01-01</td><td>5</td><td>AAPL</td></tr>
              <tr><td>Bad</td><td>2024-01-01</td><td>7</td><td>1234</td></tr>
            </table>
            """,
            {"ticker": "AAPL", "hype": 5.0, "date": "2024-01-01"},
        ),
        (
            dc,
            "insider_coll",
            "fetch_dc_insider_scores",
            """
            <table>
              <tr><th>Score</th><th>Date</th><th>Symbol</th></tr>
              <tr><td>1</td><td>2024-01-01</td><td>AAPL</td></tr>
              <tr><td>bad</td><td>2024-01-01</td><td>MSFT</td></tr>
            </table>
            """,
            {"ticker": "AAPL", "score": 1.0, "date": "2024-01-01"},
        ),
        (
            ins,
            "insider_buy_coll",
            "fetch_insider_buying",
            """
            <table>
              <tr><th>Date</th><th>Shares</th><th>Executive</th><th>Symbol</th></tr>
              <tr><td>2024-01-01</td><td>10</td><td>CEO</td><td>AAPL</td></tr>
              <tr><td>2024-01-01</td><td>5</td><td>CEO</td><td>1234</td></tr>
            </table>
            """,
            {"ticker": "AAPL", "exec": "CEO", "shares": 10, "date": "2024-01-01"},
        ),
        (
            pol,
            "politician_coll",
            "fetch_politician_trades",
            """
            <table>
              <tr><th>Amount</th><th>Politician</th><th>Date</th><th>Symbol</th><th>Type</th></tr>
              <tr><td>1</td><td>Rep</td><td>2024-01-01</td><td>AAPL</td><td>buy</td></tr>
              <tr><td>foo</td><td>Rep</td><td>2024-01-01</td><td>MSFT</td><td>sell</td></tr>
            </table>
            """,
            {
                "politician": "Rep",
                "ticker": "AAPL",
                "transaction": "buy",
                "amount": 1.0,
                "date": "2024-01-01",
            },
        ),
        (
            gc,
            "contracts_coll",
            "fetch_gov_contracts",
            """
            <table>
              <tr><th>Date</th><th>Symbol</th><th>Value</th></tr>
              <tr><td>2024-01-01</td><td>AAPL</td><td>$5</td></tr>
              <tr><td>2024-01-01</td><td>1234</td><td>$7</td></tr>
            </table>
            """,
            {"ticker": "AAPL", "value": 5.0, "date": "2024-01-01"},
        ),
    ],
)
async def test_quiver_scrapers_mapping(
    module, coll, func_name, html, expected, monkeypatch
):
    monkeypatch.setattr(module, "scrape_get", mock.AsyncMock(return_value=html))
    monkeypatch.setattr(module, coll, mock.Mock())
    monkeypatch.setattr(module, "append_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(module, "init_db", lambda: None)
    rows = await getattr(module, func_name)()
    assert len(rows) == 1
    row = rows[0]
    for key, val in expected.items():
        assert row[key] == val
    assert row["ticker"] == row["ticker"].upper()


def test_validate_row_helpers():
    row = {"ticker": "aapl", "num": "1,000"}
    out = validate_row(row, numeric_fields={"num": float})
    assert out and out["ticker"] == "AAPL" and out["num"] == 1000.0
    assert validate_row({"ticker": "1234"}) is None
    assert (
        validate_row({"ticker": "AAPL", "num": "bad"}, numeric_fields={"num": int})
        is None
    )
