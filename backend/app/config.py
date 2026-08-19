"""Filesystem locations shared by the API services."""

from pathlib import Path


def backend_root_for(module_file: str | Path) -> Path:
    """Resolve the service root for local checkouts and Vercel Services."""
    return Path(module_file).resolve().parents[1]


BACKEND_ROOT = backend_root_for(__file__)
PROJECT_ROOT = BACKEND_ROOT.parent
SIMULATOR_ROOT = BACKEND_ROOT / "simulator"
RUNTIME_ROOT = BACKEND_ROOT / "runtime"
TRACE_ROOT = RUNTIME_ROOT / "traces"
