import os
import pytest

os.environ["PG_URI"] = "postgresql://localhost/test"


def test_build_where_simple():
    database = pytest.importorskip("database")
    sql, params = database._build_where({"ticker": "AAPL"})
    assert sql == f"ticker={database.PLACEHOLDER}"
    assert params == ["AAPL"]
