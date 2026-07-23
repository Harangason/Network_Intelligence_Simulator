"""Filesystem locations shared by the API services."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
SIMULATOR_ROOT = BACKEND_ROOT / "simulator"
RUNTIME_ROOT = BACKEND_ROOT / "runtime"
TRACE_ROOT = RUNTIME_ROOT / "traces"
