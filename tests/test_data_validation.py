import pytest
import database
import infra.data_store as ds


def test_validate_docs_inconsistent_columns(monkeypatch):
    monkeypatch.setattr(database, "_table_columns", lambda *_: {"a", "b"})
    with pytest.raises(ValueError):
        database.validate_docs("t", [{"a": 1}, {"a": 1, "b": 2}])


def test_validate_docs_unknown_column(monkeypatch):
    monkeypatch.setattr(database, "_table_columns", lambda *_: {"a"})
    with pytest.raises(ValueError):
        database.validate_docs("t", [{"a": 1, "b": 2}])


def test_validate_docs_ok(monkeypatch):
    monkeypatch.setattr(database, "_table_columns", lambda *_: {"a", "b"})
    cols = database.validate_docs("t", [{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert cols == ["a", "b"]


def test_append_snapshot_validates(monkeypatch):
    monkeypatch.setattr(database, "_table_columns", lambda *_: {"a"})
    monkeypatch.setattr(ds, "backup_records", lambda *a, **k: None)
    from types import SimpleNamespace

    monkeypatch.setattr(ds, "db", SimpleNamespace(conn=None))
    with pytest.raises(ValueError):
        ds.append_snapshot("t", [{"a": 1}, {"b": 2}])
