"""48-hour retention for owned pytest runtimes, protected by process-held locks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import time

PREFIX = "nis-test-runtime-"
MARKER = ".nis-test-runtime.json"
LOCK = ".nis-test-runtime.lock"
SCHEMA = "nis-test-runtime-v1"
RETENTION_SECONDS = 48 * 60 * 60


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _claim(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _parent(path: Path) -> Path:
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError("Test runtime root must be a real, explicitly selected directory.")
    path.mkdir(parents=True, exist_ok=True)
    if _linked(path) or path.resolve() != path:
        raise ValueError("Test runtime root must be a real, explicitly selected directory.")
    return path


class RuntimeLease:
    """An OS lock is released automatically if the pytest process crashes."""

    def __init__(self, parent: Path):
        parent = _parent(parent)
        self.path = Path(tempfile.mkdtemp(prefix=PREFIX, dir=parent))
        self._handle = (self.path / LOCK).open("x+b")
        self._handle.write(b"1")
        self._handle.flush()
        _claim(self._handle)
        self._write_marker("RUNNING")

    def _write_marker(self, state: str) -> None:
        # Readers acquire the same lock first. Writing in place also avoids
        # Windows rename conflicts with filesystem indexers/scanners.
        (self.path / MARKER).write_text(
            json.dumps({"schema": SCHEMA, "directory": self.path.name,
                        "state": state, "pid": os.getpid()}), encoding="utf-8")

    def close(self) -> None:
        if not self._handle.closed:
            try:
                self._write_marker("FINISHED")
            finally:
                self._handle.close()


def cleanup_runtime_dirs(parent: Path, *, now: float | None = None) -> dict:
    """Delete expired owned trees only; foreign, linked and locked paths are kept.

    The latest directory/file write (including the FINISHED marker) starts the
    retention clock. A RUNNING marker with a released lock is a crashed session.
    """
    parent = _parent(parent)
    cutoff = (time.time() if now is None else now) - RETENTION_SECONDS
    result = {"deleted": [], "active": [], "recent": [], "unmanaged": [], "errors": []}
    for runtime in parent.iterdir():
        if not runtime.name.startswith(PREFIX):
            continue
        handle = None
        try:
            if _linked(runtime) or not runtime.is_dir() or runtime.resolve().parent != parent:
                result["unmanaged"].append(runtime.name)
                continue
            marker, lock = runtime / MARKER, runtime / LOCK
            if not marker.is_file() or not lock.is_file() or _linked(marker) or _linked(lock):
                result["unmanaged"].append(runtime.name)
                continue
            handle = lock.open("r+b")
            try:
                _claim(handle)
            except OSError:
                result["active"].append(runtime.name)
                continue
            data = json.loads(marker.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                    or data.get("directory") != runtime.name):
                result["unmanaged"].append(runtime.name)
                continue
            files, directories = [], [runtime]
            newest = runtime.stat().st_mtime
            for directory in directories:
                for child in directory.iterdir():
                    if _linked(child) or not child.resolve().is_relative_to(runtime):
                        raise ValueError("Linked or escaping child; whole runtime retained.")
                    newest = max(newest, child.stat().st_mtime)
                    if child.is_dir():
                        directories.append(child)
                    elif child.is_file():
                        files.append(child)
                    else:
                        raise ValueError("Non-regular child; whole runtime retained.")
            if newest >= cutoff:
                result["recent"].append(runtime.name)
                continue
            # Validate the complete tree before deleting anything. Keep the lock
            # held throughout content deletion; no new run reuses an old tree.
            for child in files:
                if child not in (lock, marker):
                    child.unlink()
            for directory in reversed(directories[1:]):
                directory.rmdir()
            marker.unlink()
            handle.close()
            handle = None
            lock.unlink()
            runtime.rmdir()
            result["deleted"].append(runtime.name)
        except (OSError, ValueError) as error:
            result["errors"].append({"directory": runtime.name, "error": str(error)})
        finally:
            if handle is not None:
                handle.close()
    return result
