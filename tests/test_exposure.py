from risk.exposure import gross_exposure, net_exposure


def test_exposures():
    pos = {"AAPL": 10, "MSFT": -5}
    prices = {"AAPL": 100, "MSFT": 50}
    assert gross_exposure(pos, prices) == 10*100 + 5*50
    assert net_exposure(pos, prices) == 10*100 - 5*50
