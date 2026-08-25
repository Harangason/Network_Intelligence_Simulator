"""Datenbank-Zugriff für das kanonische Engineering-Modell.

Nutzt ``psycopg`` (v3) mit einem synchronen Connection-Pool, da das Flask-
Backend selbst synchron läuft (``ThreadedWSGIServer``). Ein asynchroner
Treiber wie ``asyncpg`` würde pro Request ein eigenes Event-Loop verlangen
und wäre mit dem bestehenden Server-Modell nicht sinnvoll kombinierbar.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL ist nicht gesetzt. Das Engineering-Modul benötigt eine "
            "Neon-Postgres-Verbindung."
        )
    return url


def get_pool() -> ConnectionPool:
    """Gibt den lazily initialisierten, prozessweiten Connection-Pool zurück."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_database_url(),
            min_size=1,
            max_size=10,
            kwargs={"autocommit": False, "row_factory": dict_row},
            open=True,
        )
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
