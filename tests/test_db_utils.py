import os
import pytest

os.environ["PG_URI"] = "mysql+pymysql://localhost/test"


def test_build_where_simple():
    database = pytest.importorskip("database")
    sql, params = database._build_where({"ticker": "AAPL"})
    assert sql == f"ticker={database.PLACEHOLDER}"
    assert params == ["AAPL"]


def test_pgcollection_has_database():
    database = pytest.importorskip("database")
    assert hasattr(database.pf_coll, "database")
