import os
import re
from pathlib import Path
import pytest

os.environ["DB_URI"] = "mysql+pymysql://192.168.0.59/test"


def test_build_where_simple():
    database = pytest.importorskip("database")
    sql, params = database._build_where({"ticker": "AAPL"})
    assert sql == f"ticker={database.PLACEHOLDER}"
    assert params == ["AAPL"]


def test_pgcollection_has_database():
    database = pytest.importorskip("database")
    assert hasattr(database.pf_coll, "database")


def test_schema_analyst_ratings_has_date_before_unique():
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    text = schema_path.read_text()
    create = re.search(r"CREATE TABLE IF NOT EXISTS analyst_ratings\s*\((.*?)\);", text, re.S)
    assert create is not None
    block = create.group(1)
    assert block.index("date_utc") < block.index("UNIQUE(ticker, date_utc)")

    alters = re.findall(r"ALTER TABLE analyst_ratings(.*?);", text, re.S)
    assert alters
    ablock = alters[-1]
    assert "date_utc" in ablock
    assert ablock.index("date_utc") < ablock.index("ADD UNIQUE KEY IF NOT EXISTS uq_analyst_ratings")
