from __future__ import annotations

from contextlib import nullcontext

from backend.engineering import db


class _FakePool:
    def __init__(self, *_args, **kwargs) -> None:
        self.closed = False
        self.opened = bool(kwargs.get("open"))

    def open(self, *, wait: bool) -> None:
        assert wait is True
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def connection(self):
        return nullcontext(object())


def test_inherited_pool_is_discarded_without_touching_parent_sockets(monkeypatch) -> None:
    inherited = _FakePool()
    monkeypatch.setattr(db, "_pool", inherited)
    monkeypatch.setattr(db, "_pool_pid", 100)
    monkeypatch.setattr(db.os, "getpid", lambda: 200)
    monkeypatch.setattr(db, "ConnectionPool", _FakePool)
    monkeypatch.setattr(db, "ensure_schema", lambda _connection: None)

    pool = db.get_pool()

    assert pool is not inherited
    assert pool.opened is True
    assert inherited.closed is False
    assert db._pool_pid == 200

    db.close_pool()
    assert pool.closed is True
