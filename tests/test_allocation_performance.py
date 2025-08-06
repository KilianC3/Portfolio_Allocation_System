import pandas as pd
import numpy as np

from analytics import performance_tracking as perf


class DummyColl:
    def __init__(self):
        self.docs = []

    def update_one(self, match, update, upsert=False):
        doc = match.copy()
        doc.update(update["$set"])
        self.docs.append(doc)


def test_track_allocation_methods(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=10, freq="W")
    df = pd.DataFrame(
        {
            "A": np.random.normal(0, 0.01, len(dates)),
            "B": np.random.normal(0, 0.02, len(dates)),
        },
        index=dates,
    )
    coll = DummyColl()
    monkeypatch.setattr(perf, "alloc_perf_coll", coll)
    res = perf.track_allocation_performance(df)
    assert set(res) == {
        "max_sharpe",
        "risk_parity",
        "min_variance",
        "saa",
        "taa",
        "dynamic",
    }
    assert len(coll.docs) == 6
