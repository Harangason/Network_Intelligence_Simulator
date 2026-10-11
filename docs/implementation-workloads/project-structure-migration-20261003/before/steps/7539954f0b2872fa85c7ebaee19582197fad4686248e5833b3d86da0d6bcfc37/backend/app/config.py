"""Filesystem locations shared by the API services."""

import os
from collections.abc import Mapping
from pathlib import Path


def backend_root_for(module_file: str | Path) -> Path:
    """Resolve the service root for local checkouts and Vercel Services."""
    return Path(module_file).resolve().parents[1]


def runtime_root_for(
    backend_root: Path,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Use writable ephemeral storage inside Vercel functions."""
    values = os.environ if environment is None else environment
    if configured := values.get("SIMULATOR_RUNTIME_ROOT"):
        return Path(configured).expanduser().resolve()
    if values.get("VERCEL"):
        return Path("/tmp/communication-simulator")
    return backend_root / "runtime"


BACKEND_ROOT = backend_root_for(__file__)
PROJECT_ROOT = BACKEND_ROOT.parent
SIMULATOR_ROOT = BACKEND_ROOT / "simulator"
RUNTIME_ROOT = runtime_root_for(BACKEND_ROOT)
TRACE_ROOT = RUNTIME_ROOT / "traces"
