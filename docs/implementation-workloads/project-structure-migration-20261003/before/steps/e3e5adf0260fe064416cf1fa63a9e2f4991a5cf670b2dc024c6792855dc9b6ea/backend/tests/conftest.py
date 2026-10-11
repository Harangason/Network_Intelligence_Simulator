"""Make the relocated flat simulator modules importable during tests."""

import os
import re
import sys
import warnings
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest


SIMULATOR_ROOT = Path(__file__).resolve().parents[1] / "simulator"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(SIMULATOR_ROOT))

from scripts.test_runtime_storage import RuntimeLease, cleanup_runtime_dirs


def _safe_test_database_url(value: str) -> str:
    normalized = value.replace("postgresql+psycopg://", "postgresql://", 1)
    parts = urlsplit(normalized)
    if parts.scheme not in {"postgres", "postgresql"} or not re.fullmatch(
        r"/(?:nis_test_[a-z0-9_]+|nis_bus_naming_tests)", parts.path
    ):
        raise pytest.UsageError("Tests refuse this database. Use scripts/run-isolated-tests.py; product DSNs are forbidden.")
    return normalized


def pytest_configure(config):
    """Fail before test-module imports can open a product database."""
    approved = os.environ.get("ENGINEERING_TEST_DATABASE_URL", "")
    configured = os.environ.get("DATABASE_URL", "")
    if approved:
        safe = _safe_test_database_url(approved)
        if configured and _safe_test_database_url(configured) != safe:
            raise pytest.UsageError("DATABASE_URL must equal ENGINEERING_TEST_DATABASE_URL during tests.")
        os.environ["DATABASE_URL"] = safe
    elif configured:
        raise pytest.UsageError("An explicit ENGINEERING_TEST_DATABASE_URL is required; product DSNs are forbidden.")
    else:
        # Pure unit suites remain usable without Postgres. Accidental SQL cannot
        # fall back to a developer database or establish a real connection.
        os.environ["DATABASE_URL"] = "postgresql://nis_test:disabled@127.0.0.1:1/nis_test_disabled"
    runtime_parent = PROJECT_ROOT / "traces" / "temp"
    cleanup = cleanup_runtime_dirs(runtime_parent)
    config._nis_runtime_cleanup = cleanup
    if cleanup["deleted"] or cleanup["errors"]:
        print(f"NIS test runtime cleanup: {len(cleanup['deleted'])} expired directories removed; "
              f"{len(cleanup['active'])} active protected; {len(cleanup['errors'])} errors.")
    lease = RuntimeLease(runtime_parent)
    runtime = str(lease.path)

    def finish_runtime():
        try:
            lease.close()
        except OSError as error:
            warnings.warn(f"Could not mark test runtime finished: {error}", RuntimeWarning)

    config.add_cleanup(finish_runtime)
    os.environ["SIMULATOR_RUNTIME_ROOT"] = runtime
    os.environ["NUMERIC_ACCELERATOR"] = "cpu"
    config._nis_test_runtime = runtime


@pytest.fixture(autouse=True)
def isolated_project_context():
    """Unscoped test helpers must never read/write the shared default project."""
    from backend.engineering.project_context import activate_project, reset_project
    token = activate_project("pytest-isolated-" + uuid4().hex)
    try:
        yield
    finally:
        reset_project(token)
