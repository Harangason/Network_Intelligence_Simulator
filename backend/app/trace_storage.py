"""Project-scoped output locations; existing jobs retain their original location."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path, PureWindowsPath

from .config import RUNTIME_ROOT, TRACE_ROOT
from .saved_storage import saved_root, project_folder
from ..engineering.project_context import normalize_context_project_id


class StorageError(ValueError):
    pass


class StorageUnavailable(StorageError):
    pass


_SETTINGS_LOCK = threading.RLock()


class TraceStorage:
    def __init__(self, *, default_root=None, settings_path=None, container=None, host_path=None, mount_path=None):
        self.project_defaults = default_root is None
        self.default_root = Path(default_root or saved_root()).resolve()
        self.settings_path = Path(settings_path or RUNTIME_ROOT / "storage" / "trace-storage.json")
        self.container = Path("/.dockerenv").exists() if container is None else container
        self.host_path = host_path if host_path is not None else os.environ.get("NETWORKIS_TRACE_HOST_PATH", "")
        self.mount_path = Path(mount_path or os.environ.get("NETWORKIS_TRACE_MOUNT_PATH", "/trace-output")).resolve()

    def _read(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
                raise ValueError("invalid settings")
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise StorageUnavailable("Speicher-Einstellungen sind nicht lesbar. Es wird kein Ersatzpfad verwendet.") from exc

    def _roots(self):
        roots = [self.default_root, TRACE_ROOT.resolve()]
        if self.container and self.host_path and self.mount_path.is_dir():
            roots.append(self.mount_path)
        return roots

    def display_path(self, path):
        path = Path(path)
        if self.container and self.host_path and path.is_relative_to(self.mount_path):
            relative = path.relative_to(self.mount_path)
            if PureWindowsPath(self.host_path).is_absolute():
                return str(PureWindowsPath(self.host_path).joinpath(*relative.parts))
            return str(Path(self.host_path) / relative)
        return str(path)

    def resolve(self, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 4096 or "\x00" in value:
            raise StorageError("Bitte einen vollständigen absoluten Ordnerpfad angeben.")
        value = value.strip()
        windows = PureWindowsPath(value)
        if self.container and self.host_path:
            host = PureWindowsPath(self.host_path)
            if windows.is_absolute() and host.is_absolute() and windows.is_relative_to(host):
                value = str(self.mount_path.joinpath(*windows.relative_to(host).parts))
            elif not host.is_absolute() and Path(value).is_absolute() and Path(value).is_relative_to(Path(self.host_path)):
                value = str(self.mount_path / Path(value).relative_to(Path(self.host_path)))
        if os.name != "nt" and (PureWindowsPath(value).drive or "\\" in value):
            raise StorageError("Dieser Windows-Ordner ist nicht eingebunden. Im Docker-Betrieb zuerst den gewünschten Host-Ordner als /trace-output einbinden.")
        path = Path(value)
        if not path.is_absolute():
            raise StorageError("Relative Pfade sind nicht erlaubt. Bitte einen absoluten Ordnerpfad wählen.")
        try:
            path = path.resolve()
        except (OSError, RuntimeError) as exc:
            raise StorageError("Der Ordnerpfad kann nicht aufgelöst werden.") from exc
        if self.container and not any(path.is_relative_to(root) for root in self._roots()):
            raise StorageError("Bitte einen Ordner im Trace-Volume oder im eingebundenen Host-Ordner wählen.")
        return path

    def _check(self, path, *, create=False):
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            probe_root = path
            while not probe_root.exists() and probe_root != probe_root.parent:
                probe_root = probe_root.parent
            if not probe_root.is_dir():
                raise StorageError("Der Speicherpfad muss ein Ordner sein, keine Datei.")
            with tempfile.TemporaryFile(prefix=".networkis-write-check-", dir=probe_root) as probe:
                probe.write(b"networkis")
                probe.flush()
                os.fsync(probe.fileno())
            return {"path": self.display_path(path), "resolved_path": str(path), "exists": path.is_dir(),
                    "free_bytes": shutil.disk_usage(probe_root).free}
        except OSError as exc:
            raise StorageUnavailable(f"Speicherordner ist nicht verfügbar oder nicht beschreibbar: {path}") from exc

    def validate(self, value):
        return self._check(self.resolve(value))

    def root_for(self, project_id):
        with _SETTINGS_LOCK:
            value = self._read().get(normalize_context_project_id(project_id))
        return self.resolve(value) if value else (project_folder(project_id) / 'runs' if self.project_defaults else self.default_root)

    def settings(self, project_id):
        project_id = normalize_context_project_id(project_id)
        root = self.root_for(project_id)
        return {"project_id": project_id, "path": self.display_path(root), "resolved_path": str(root),
                "default_path": self.display_path(project_folder(project_id) / 'runs' if self.project_defaults else self.default_root), "is_default": root == (project_folder(project_id) / 'runs' if self.project_defaults else self.default_root),
                "container": self.container, "roots": [self.display_path(p) for p in self._roots()],
                "host_folder_connected": bool(self.container and self.host_path and self.mount_path.is_dir())}

    def save(self, project_id, value):
        path = self.default_root if value is None else self.resolve(value)
        self._check(path, create=True)
        with _SETTINGS_LOCK:
            data = self._read()
            key = normalize_context_project_id(project_id)
            if path == self.default_root:
                data.pop(key, None)
            else:
                data[key] = str(path)
            temporary = None
            try:
                self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.settings_path.parent,
                                                 prefix="trace-storage-", suffix=".tmp", delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.settings_path)
            except OSError as exc:
                raise StorageUnavailable("Speicherpfad konnte nicht dauerhaft gespeichert werden.") from exc
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return self.settings(project_id)

    def output_for(self, project_id, job_id):
        root = self.root_for(project_id)
        self._check(root, create=True)
        return root / job_id

    def directories(self, project_id, value=None):
        path = self.resolve(value) if value else self.root_for(project_id)
        try:
            entries = []
            with os.scandir(path) as iterator:
                for entry in iterator:
                    if entry.name.startswith(".") or entry.is_symlink() or not entry.is_dir():
                        continue
                    entries.append({"name": entry.name, "path": self.display_path(Path(entry.path))})
                    if len(entries) >= 201:
                        break
            parent = path.parent
            if self.container and not any(parent.is_relative_to(root) for root in self._roots()):
                parent = None
            return {"path": self.display_path(path), "parent": self.display_path(parent) if parent and parent != path else None,
                    "directories": sorted(entries[:200], key=lambda item: item["name"].casefold()), "truncated": len(entries) > 200}
        except OSError as exc:
            raise StorageUnavailable("Dieser Ordner kann nicht gelesen werden.") from exc
