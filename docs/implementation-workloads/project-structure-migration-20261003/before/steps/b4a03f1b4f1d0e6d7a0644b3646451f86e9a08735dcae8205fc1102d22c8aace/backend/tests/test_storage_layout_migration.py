import sqlite3

import pytest

from scripts.migrations.storage_layout import copy_verified, sqlite_contents


def test_sqlite_backup_includes_wal_and_preserves_original(tmp_path):
    source = tmp_path / "active.db"
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE records (value TEXT)")
        writer.execute("INSERT INTO records VALUES ('retained')")
        writer.commit()
        target = tmp_path / "data/copied.db"
        receipt = copy_verified(source, target)
        assert sqlite_contents(target)["tables"] == {"records": 1}
        assert receipt["original_retained"]
        assert writer.execute("SELECT value FROM records").fetchone() == ("retained",)


def test_different_destination_never_overwritten(tmp_path):
    source = tmp_path / "original.json"
    target = tmp_path / "destination.json"
    source.write_text("source")
    target.write_text("user changes")
    with pytest.raises(FileExistsError):
        copy_verified(source, target)
    assert target.read_text() == "user changes"
    assert source.read_text() == "source"


def test_same_data_is_idempotent(tmp_path):
    source = tmp_path / "original.json"
    target = tmp_path / "data/copied.json"
    source.write_text("retained")
    assert copy_verified(source, target) == copy_verified(source, target)
