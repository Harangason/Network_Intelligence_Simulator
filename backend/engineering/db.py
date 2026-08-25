"""Datenbank-Zugriff für das kanonische Engineering-Modell.

Nutzt ``psycopg`` (v3) mit einem synchronen Connection-Pool, da das Flask-
Backend selbst synchron läuft (``ThreadedWSGIServer``). Ein asynchroner
Treiber wie ``asyncpg`` würde pro Request ein eigenes Event-Loop verlangen
und wäre mit dem bestehenden Server-Modell nicht sinnvoll kombinierbar.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .schema import ensure_schema

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()
DEFAULT_CONNECT_TIMEOUT_SECONDS = 2.0


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL ist nicht gesetzt. Das Engineering-Modul benötigt eine "
            "Neon-Postgres-Verbindung."
        )
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _timeout_seconds(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} muss eine Zahl sein.") from error
    if value <= 0:
        raise RuntimeError(f"{name} muss größer als 0 sein.")
    return value


def get_pool() -> ConnectionPool:
    """Gibt den lazily initialisierten, prozessweiten Connection-Pool zurück."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        timeout = _timeout_seconds("ENGINEERING_DB_TIMEOUT", DEFAULT_CONNECT_TIMEOUT_SECONDS)
        candidate = ConnectionPool(
            conninfo=_database_url(),
            min_size=1,
            max_size=10,
            timeout=timeout,
            kwargs={"autocommit": False, "connect_timeout": timeout, "row_factory": dict_row},
            open=True,
        )
        try:
            with candidate.connection() as connection:
                ensure_schema(connection)
        except Exception:
            candidate.close()
            raise
        _pool = candidate
    return _pool


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Kontext-Manager, der eine Connection aus dem Pool ausleiht.

    Committet automatisch bei erfolgreichem Verlassen des Blocks und rollt bei
    Exceptions zurück.
    """
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    """Schließt den Connection-Pool (z. B. für Tests/Teardown)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
