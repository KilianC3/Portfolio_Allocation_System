import pandas as pd
import numpy as np
import datetime as dt
from analytics.robust import minmax_portfolio
from analytics.covariance import estimate_covariance
from analytics.utils import portfolio_metrics, portfolio_correlations
from analytics.allocation_engine import compute_weights
from pathlib import Path


def test_all_models():
    cov = pd.DataFrame([[0.1, 0.05], [0.05, 0.2]], index=["A", "B"], columns=["A", "B"])
    mu = pd.Series([0.02, 0.03], index=["A", "B"])
    mm = minmax_portfolio(mu, cov)
    rand = pd.DataFrame(np.random.randn(50, 2), columns=["A", "B"])
    cov_est = estimate_covariance(rand)
    metrics = portfolio_metrics(pd.Series(np.random.randn(50)))
    for k in ["weekly_vol", "weekly_sortino", "atr_14d", "rsi_14d"]:
        assert k in metrics
    assert not cov_est.isna().any().any()
    assert not mm.isna().any()
    print(mm.iloc[0], list(metrics.values())[0])


def test_fama_french_expected_return():
    r = pd.Series([0.001, 0.002, 0.003])
    mkt = pd.Series([0.001, 0.002, 0.003])
    smb = pd.Series([0.0005, 0.0005, 0.0005])
    hml = pd.Series([-0.0002, -0.0002, -0.0002])
    factors = pd.DataFrame({"mkt": mkt, "smb": smb, "hml": hml})
    metrics = portfolio_metrics(r, factors, rf=0.0)
    assert "ff_expected_return" in metrics
    expected = (
        metrics["beta"] * (mkt.mean() * 252)
        + metrics["beta_smb"] * (smb.mean() * 252)
        + metrics["beta_hml"] * (hml.mean() * 252)
    )
    assert abs(metrics["ff_expected_return"] - expected) < 1e-6


from strategies.smallcap_momentum import SmallCapMomentum


def test_biotech_check(monkeypatch):
    class FakeTicker:
        info = {"industry": "Biotechnology"}

    monkeypatch.setattr("yfinance.Ticker", lambda s: FakeTicker())
    assert SmallCapMomentum.is_biotech("AAPL")


def test_update_ticker_scores(monkeypatch):
    import analytics.tracking as trk

    dates = pd.date_range("2020-01-01", periods=10)

    def fake_download(symbols, *a, **k):
        syms = symbols if isinstance(symbols, list) else [symbols]
        close = pd.DataFrame({s: np.linspace(1, 2, 10) for s in syms}, index=dates)
        return pd.concat({"Close": close}, axis=1)

    monkeypatch.setattr(trk.yf, "download", fake_download)
    rec = []

    class Coll:
        def update_one(self, *a, **k):
            rec.append(a)

    monkeypatch.setattr(trk, "ticker_score_coll", Coll())
    monkeypatch.setattr(
        trk,
        "compute_fundamental_metrics",
        lambda s: {
            "piotroski": 5,
            "altman": 3,
            "roic": 10,
            "fcf_yield": 5,
            "beneish": -1,
            "short_ratio": 0.1,
            "insider_buying": 1,
        },
    )
    trk.update_ticker_scores(["AAPL"], "S&P500")
    assert rec and rec[0][1]["$set"]["index_name"] == "S&P500"


def test_record_top_scores(monkeypatch):
    import analytics.tracking as trk

    data = [
        {
            "symbol": "AAPL",
            "index_name": "S&P500",
            "score": 9.0,
            "date": dt.date(2024, 1, 1),
        },
        {
            "symbol": "MSFT",
            "index_name": "S&P500",
            "score": 8.5,
            "date": dt.date(2024, 1, 1),
        },
    ]

    class ScoreColl(list):
        def find(self, *a, **k):
            return self

        def find_one(self, *a, **k):
            return {"date": dt.date(2024, 1, 1)}

    class TopColl:
        def __init__(self):
            self.rows = []

        def delete_many(self, q):
            pass

        def update_one(self, match, update, upsert=False):
            self.rows.append(update["$set"])

    top = TopColl()
    monkeypatch.setattr(trk, "ticker_score_coll", ScoreColl(data))
    monkeypatch.setattr(trk, "top_score_coll", top)

    trk.record_top_scores(2)
    assert len(top.rows) == 2 and top.rows[0]["symbol"] == "AAPL"


def test_compute_weights_simple():
    dates = pd.date_range("2024-01-01", periods=90)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.01, len(dates)),
        },
        index=dates,
    )
    w = compute_weights(df)
    assert abs(sum(w.values()) - 1) < 1e-6 and set(w) == {"A", "B"}


def test_compute_weights_various_methods():
    dates = pd.date_range("2024-01-01", periods=90)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.02, len(dates)),
        },
        index=dates,
    )
    for m in ["risk_parity", "min_variance", "saa", "taa", "dynamic"]:
        w = compute_weights(df, method=m)
        assert abs(sum(w.values()) - 1) < 1e-6


def test_compute_weights_anomaly():
    dates = pd.date_range("2024-01-01", periods=90)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 5.0, len(dates)),
            "B": np.random.normal(0, 5.0, len(dates)),
        },
        index=dates,
    )
    prev = {"A": 0.6, "B": 0.4}
    w = compute_weights(df, w_prev=prev)
    assert w == prev


def test_compute_weights_insufficient_data():
    dates = pd.date_range("2024-01-01", periods=14)
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.01, len(dates)),
            "C": np.random.normal(0, 0.01, len(dates)),
        },
        index=dates,
    )
    w = compute_weights(df)
    assert all(abs(v - 1 / 3) < 1e-6 for v in w.values())


def test_portfolio_correlations():
    df = pd.DataFrame(
        {
            "A": [0.1, 0.2, 0.3],
            "B": [0.1, 0.2, 0.3],
            "C": [0.3, 0.2, 0.1],
        }
    )
    corr = portfolio_correlations(df)
    assert corr.loc["A", "B"] == 1.0


def test_sector_exposures(monkeypatch):
    class FakeTicker:
        def __init__(self, sector):
            self.info = {"sector": sector}

    def fake_ticker(sym: str):
        return FakeTicker({"A": "Tech", "B": "Health"}.get(sym, "Other"))

    monkeypatch.setattr("analytics.utils.yf.Ticker", lambda s: fake_ticker(s))
    from analytics.utils import sector_exposures

    exp = sector_exposures({"A": 0.6, "B": 0.4})
    assert abs(exp["Tech"] - 0.6) < 1e-6
    assert abs(exp["Health"] - 0.4) < 1e-6


def test_small_cap_portfolios():
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "sector": ["Tech", "Tech", "Health", "Health"],
            "market_cap": [150_000_000] * 4,
            "avg_dollar_volume": [6_000_000] * 4,
            "composite_score": [10, 9, 8, 7],
            "free_cash_flow_ttm": [1] * 4,
            "ROE": [5] * 4,
            "return_3m": [5] * 4,
            "bid_ask_spread": [1] * 4,
            "vol_30d": [10] * 4,
        }
    )

    from strategies.small_cap_portfolios import (
        build_sector_neutral_portfolio,
        build_micro_small_composite_leaders,
    )

    w1 = build_sector_neutral_portfolio(df, top_n_per_sector=1)
    assert w1 == {"A": 0.5, "C": 0.5}

    w2 = build_micro_small_composite_leaders(df.head(3))
    assert abs(sum(w2.values()) - 1) < 1e-6 and w2


def test_cci_scaling_and_weights():
    from risk.crisis import compute_cci, cci_scaling, scale_weights

    data = pd.DataFrame(
        {
            "s1": [1, 2, 3, 4, 5],
            "s2": [2, 3, 4, 5, 6],
        },
        index=pd.date_range("2020-01-01", periods=5),
    )
    weights = {"s1": 0.5, "s2": 0.5}
    cci_series = compute_cci(data, weights)
    cci = float(cci_series.iloc[-1])
    scale = cci_scaling(cci)
    scaled = scale_weights({"A": 0.6, "B": 0.4}, cci)
    assert 0.3 <= scale <= 1.0
    assert all(
        abs(v - scale * orig) < 1e-6 for v, orig in zip(scaled.values(), [0.6, 0.4])
    )
