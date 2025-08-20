import datetime as dt
from types import SimpleNamespace

import pytest

import service.api as api


class DummyQuery:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def __iter__(self):
        return iter(self.rows)


@pytest.mark.parametrize(
    "attr,func,extra",
    [
        ("vol_mom_coll", api.show_vol_mom, {"score": 1.0, "ret_52w": 2.0, "vol_12w": 0.5}),
        ("lev_sector_coll", api.show_lev_sector, {"ret": 0.2}),
        ("sector_mom_coll", api.show_sector_mom, {"ret": 0.1}),
        ("smallcap_mom_coll", api.show_smallcap_mom, {"price": 10.0, "ret": 0.05}),
        (
            "upgrade_mom_coll",
            api.show_upgrade_mom,
            {"ratio": 0.5, "upgrades": 1, "downgrades": 0, "total": 1},
        ),
    ],
)
def test_momentum_endpoints_return_metrics(monkeypatch, attr, func, extra):
    now = dt.datetime(2024, 1, 1)
    sample = {"_id": 1, "symbol": "TST", "_retrieved": now, **extra}
    monkeypatch.setattr(api, attr, SimpleNamespace(find=lambda *a, **k: DummyQuery([sample])))
    out = func()
    rec = out["records"][0]
    assert "id" not in rec and "_id" not in rec
    assert rec["symbol"] == "TST"
    for k in extra:
        assert k in rec
