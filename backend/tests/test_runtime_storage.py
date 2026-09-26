"""Filesystem-only regressions for test output retention; no database needed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from scripts.test_runtime_storage import (
    LOCK, MARKER, PREFIX, RETENTION_SECONDS, RuntimeLease, cleanup_runtime_dirs,
)


def age_tree(root, timestamp):
    for path in root.rglob("*"):
        os.utime(path, (timestamp, timestamp))
    os.utime(root, (timestamp, timestamp))


def finished_runtime(parent):
    lease = RuntimeLease(parent)
    nested = lease.path / "traces" / "session"
    nested.mkdir(parents=True)
    (nested / "source.trace").write_bytes(b"test capture")
    lease.close()
    return lease.path


def test_expired_finished_tree_removed(tmp_path):
    runtime = finished_runtime(tmp_path)
    now = time.time()
    age_tree(runtime, now - RETENTION_SECONDS - 10)
    result = cleanup_runtime_dirs(tmp_path, now=now)
    assert result["deleted"] == [runtime.name]
    assert result["errors"] == []
    assert not runtime.exists()


@pytest.mark.parametrize("age", [0, RETENTION_SECONDS])
def test_recent_and_exact_boundary_retained(tmp_path, age):
    runtime = finished_runtime(tmp_path)
    now = int(time.time())
    age_tree(runtime, now - age)
    result = cleanup_runtime_dirs(tmp_path, now=now)
    assert result["recent"] == [runtime.name]
    assert (runtime / "traces" / "session" / "source.trace").exists()


def test_recent_child_extends_retention(tmp_path):
    runtime = finished_runtime(tmp_path)
    now = time.time()
    age_tree(runtime, now - RETENTION_SECONDS - 10)
    os.utime(runtime / "traces" / "session" / "source.trace", (now, now))
    assert cleanup_runtime_dirs(tmp_path, now=now)["recent"] == [runtime.name]


def test_active_process_protected_then_crash_releases_lock(tmp_path):
    code = (
        "from pathlib import Path; import sys; "
        "from scripts.test_runtime_storage import RuntimeLease; "
        "lease = RuntimeLease(Path(sys.argv[1])); "
        "print(lease.path, flush=True); sys.stdin.read()"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        runtime = Path(process.stdout.readline().strip())
        assert runtime.parent == tmp_path
        now = time.time()
        age_tree(runtime, now - RETENTION_SECONDS - 10)
        assert cleanup_runtime_dirs(tmp_path, now=now)["active"] == [runtime.name]
        assert runtime.is_dir()
        process.kill()
        process.wait(timeout=10)
        assert json.loads((runtime / MARKER).read_text())["state"] == "RUNNING"
        assert cleanup_runtime_dirs(tmp_path, now=now)["deleted"] == [runtime.name]
        assert not runtime.exists()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def test_foreign_and_unmarked_paths_retained(tmp_path):
    for name in [PREFIX + "legacy", "unrelated"]:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "keep.txt").write_text("keep")
        age_tree(directory, time.time() - RETENTION_SECONDS - 10)
    result = cleanup_runtime_dirs(tmp_path)
    assert result["deleted"] == []
    assert result["unmanaged"] == [PREFIX + "legacy"]
    assert len(list(tmp_path.rglob("keep.txt"))) == 2


@pytest.mark.parametrize("contents", ["[]", '{"schema":"foreign"}', "broken json"])
def test_bad_marker_preserved_and_other_cleanup_continues(tmp_path, contents):
    invalid = finished_runtime(tmp_path)
    (invalid / MARKER).write_text(contents)
    valid = finished_runtime(tmp_path)
    now = time.time()
    for runtime in [invalid, valid]:
        age_tree(runtime, now - RETENTION_SECONDS - 10)
    result = cleanup_runtime_dirs(tmp_path, now=now)
    assert result["deleted"] == [valid.name]
    assert (invalid / "traces" / "session" / "source.trace").exists()


def test_junction_child_keeps_whole_tree_and_external_target(tmp_path):
    parent = tmp_path / "managed"
    runtime = finished_runtime(parent)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("untouched")
    age_tree(runtime, time.time() - RETENTION_SECONDS - 10)
    link = runtime / "external"
    if os.name == "nt":
        # Both paths come from pytest's private temporary directory.
        script = "New-Item -ItemType Junction -Path $env:NIS_TEST_LINK -Target $env:NIS_TEST_TARGET | Out-Null"
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True,
                       env={**os.environ, "NIS_TEST_LINK": str(link), "NIS_TEST_TARGET": str(outside)},
                       capture_output=True, text=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        result = cleanup_runtime_dirs(parent, now=time.time() + RETENTION_SECONDS + 100)
        assert result["deleted"] == []
        assert result["errors"][0]["directory"] == runtime.name
        assert (runtime / "traces" / "session" / "source.trace").exists()
        assert sentinel.read_text() == "untouched"
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def test_pytest_session_has_owned_locked_project_runtime(request):
    runtime = Path(request.config._nis_test_runtime)
    assert runtime.parent == Path(__file__).resolve().parents[2] / "traces" / "temp"
    assert json.loads((runtime / MARKER).read_text())["state"] == "RUNNING"
    assert (runtime / LOCK).is_file()
