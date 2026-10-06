"""Filesystem locations shared by the API services."""

import os
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path


def backend_root_for(module_file: str | Path) -> Path:
    """Resolve the service root for local checkouts and Vercel Services."""
    resolved = Path(module_file).resolve()
    return next((parent for parent in resolved.parents if parent.name == "backend"), resolved.parents[1])


@dataclass(frozen=True)
class StoragePaths:
    data: Path
    runtime: Path
    artifacts: Path


def storage_paths_for(backend_root: Path, environment: Mapping[str, str] | None = None) -> StoragePaths:
    """Resolve every storage class against the checkout, never the launch cwd.

    Existing explicit runtime roots keep their durable contents during transition.
    Production sets explicit roots before its volume layout is migrated.
    """
    values = os.environ if environment is None else environment
    project = backend_root.resolve().parent

    def configured(key: str, default: Path) -> Path:
        value = values.get(key)
        if not value:
            return default
        path = Path(value).expanduser()
        return (path if path.is_absolute() else project / path).resolve()

    legacy = configured("SIMULATOR_RUNTIME_ROOT", project / "var/runtime")
    ephemeral = Path("/tmp/communication-simulator") if values.get("VERCEL") else project / "var/runtime"
    runtime = configured("NIS_RUNTIME_DIR", legacy if values.get("SIMULATOR_RUNTIME_ROOT") else ephemeral)
    data_default = legacy if values.get("SIMULATOR_RUNTIME_ROOT") else (
        ephemeral / "data" if values.get("VERCEL") else project / "var/data")
    return StoragePaths(configured("NIS_DATA_DIR", data_default), runtime,
                        configured("NIS_ARTIFACTS_DIR", ephemeral / "artifacts" if values.get("VERCEL") else project / "artifacts"))


def runtime_root_for(
    backend_root: Path,
    environment: Mapping[str, str] | None = None,
) -> Path:
    return storage_paths_for(backend_root, environment).runtime


BACKEND_ROOT = backend_root_for(__file__)
PROJECT_ROOT = BACKEND_ROOT.parent
SIMULATOR_ROOT = BACKEND_ROOT / "simulator"
STORAGE = storage_paths_for(BACKEND_ROOT)
DATA_ROOT = STORAGE.data
RUNTIME_ROOT = STORAGE.runtime
ARTIFACTS_ROOT = STORAGE.artifacts
DATABASE_ROOT = DATA_ROOT / "databases"
LEARNING_ROOT = DATA_ROOT / "learning"
MODELS_ROOT = DATA_ROOT / "ml_registry"
TRACE_ROOT = DATA_ROOT / "traces"
EXPORT_ROOT = ARTIFACTS_ROOT / "exports"


def migrated_data_path(value: str) -> str:
    """Rebase only confirmed old volume paths whose retained target exists."""
    legacy = os.environ.get("NIS_LEGACY_DATA_ROOT")
    if not legacy:
        return value
    original, previous = Path(value), Path(legacy)
    if not original.is_absolute() or not original.is_relative_to(previous):
        return value
    relative = original.relative_to(previous)
    if ".." in relative.parts:
        return value
    target = DATA_ROOT / relative
    return str(target) if target.exists() else value
