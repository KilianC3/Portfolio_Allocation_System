from scrapers import full_fundamentals as ff


def test_fetch_fundamentals_live():
    data = ff.fetch_fundamentals("AAPL")
    assert isinstance(data, dict)
    assert data


def test_collect_fundamentals_live():
    result = ff.collect_fundamentals("AAPL")
    assert isinstance(result, dict)
    assert result
    assert "piotroski" in result
