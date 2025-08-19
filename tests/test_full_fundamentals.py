import pytest

from scrapers import full_fundamentals as ff

# Live fundamental fetches hit external APIs and can stall CI if the network
# is slow or unavailable. Skip these smoke tests in automated runs.
pytestmark = pytest.mark.skip(reason="requires network access to yfinance")


def test_fetch_fundamentals_live():
    data = ff.fetch_fundamentals("AAPL")
    assert isinstance(data, dict)
    assert data


def test_collect_fundamentals_live():
    result = ff.collect_fundamentals("AAPL")
    assert isinstance(result, dict)
    assert result
    assert "piotroski" in result
