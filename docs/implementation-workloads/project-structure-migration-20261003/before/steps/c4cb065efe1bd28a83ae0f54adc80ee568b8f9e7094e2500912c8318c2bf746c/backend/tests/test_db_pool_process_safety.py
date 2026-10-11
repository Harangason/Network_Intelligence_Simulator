from __future__ import annotations

from contextlib import nullcontext
import threading

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


class _FakeConnection:
    def execute(self, *_args, **_kwargs):
        return self


class _FakeConnectionContext:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def __enter__(self):
        return self.connection

    def __exit__(self, *_args):
        return False


class _RequestPool:
    def connection(self):
        return _FakeConnectionContext()


def test_project_mutations_wait_locally_before_consuming_a_database_lock(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_pool", lambda: _RequestPool())
    monkeypatch.setenv("ENGINEERING_PROJECT_LOCK_TIMEOUT", "0.02")
    first = db.RequestUnit("serialized-project")
    first.acquire()
    failure: list[Exception] = []

    def contend() -> None:
        second = db.RequestUnit("serialized-project")
        try:
            second.acquire()
        except Exception as error:  # captured for assertion in the parent thread
            failure.append(error)
        finally:
            second.close()

    thread = threading.Thread(target=contend)
    thread.start()
    thread.join(timeout=1)
    first.finish(True)
    first.close()

    assert not thread.is_alive()
    assert len(failure) == 1
    assert isinstance(failure[0], db.ConcurrentUpdateError)


def test_project_mutation_lock_is_released_after_commit(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_pool", lambda: _RequestPool())
    first = db.RequestUnit("released-project")
    first.acquire()
    first.finish(True)
    first.close()

    second = db.RequestUnit("released-project")
    assert second.acquire() is not None
    second.finish(True)
    second.close()
