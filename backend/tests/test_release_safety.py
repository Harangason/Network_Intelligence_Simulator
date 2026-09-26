"""Exercise entry-point refusal before any database or deployment work starts."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_build_manifest_records_base_revision_separately_from_changed_source(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('build_identity', ROOT / 'scripts/write-build-info.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv('NIS_BUILD_COMMIT_ID', raising=False)
    assert module.build_manifest(tmp_path)['commit_id'] is None
    base_commit = 'a' * 40
    monkeypatch.setenv('NIS_BUILD_COMMIT_ID', base_commit)
    before = module.build_manifest(tmp_path)
    source = tmp_path / 'backend' / 'app.py'
    source.parent.mkdir()
    source.write_text('changed = True\n')
    after = module.build_manifest(tmp_path)
    assert before['commit_id'] == after['commit_id'] == base_commit
    assert before['source_sha256'] != after['source_sha256']
    monkeypatch.setenv('NIS_BUILD_COMMIT_ID', 'unknown')
    with pytest.raises(ValueError, match='full Git object ID'):
        module.build_manifest(tmp_path)
    (tmp_path / '.git').mkdir()
    monkeypatch.setenv('NIS_BUILD_COMMIT_ID', base_commit)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **kw: 'b' * 40)
    with pytest.raises(ValueError, match='checkout HEAD'):
        module.build_manifest(tmp_path)


def test_release_manifest_tracks_agent_runtime_code_but_not_runtime_data(tmp_path):
    spec = importlib.util.spec_from_file_location('build_info', ROOT / 'scripts/write-build-info.py')
    build_info = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_info)
    agent_code = tmp_path / 'backend/agent_core/runtime/goal_resolver.py'
    agent_code.parent.mkdir(parents=True)
    agent_code.write_text('version = 1\n')
    runtime_data = tmp_path / 'backend/runtime/state.py'
    runtime_data.parent.mkdir(parents=True)
    runtime_data.write_text('version = 1\n')
    initial = build_info.build_manifest(tmp_path)['source_sha256']
    runtime_data.write_text('version = 2\n')
    assert build_info.build_manifest(tmp_path)['source_sha256'] == initial
    agent_code.write_text('version = 2\n')
    assert build_info.build_manifest(tmp_path)['source_sha256'] != initial


def test_runtime_lock_rejects_unlocked_transitives_and_version_drift():
    spec = importlib.util.spec_from_file_location('runtime_lock', ROOT / 'scripts/verify-runtime-lock.py')
    lock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lock)
    expected = lock.parse_pins('# frozen runtime\nPackage_A==1.0\npackage-b==2.0\n')
    assert lock.differences(expected, lock.parse_pins('package-a==1.0\npackage_b==2.0')) == []
    actual = lock.parse_pins('package-a==1.1\nunlocked-transitive==3.0')
    assert lock.differences(expected, actual) == [
        'package-a: locked=1.0, installed=1.1',
        'package-b: locked=2.0, installed=MISSING',
        'unlocked-transitive: locked=MISSING, installed=3.0',
    ]
    with pytest.raises(ValueError, match='Duplicate'):
        lock.parse_pins('package-A==1.0\npackage_a==1.0')
    with pytest.raises(ValueError, match='exact package pin'):
        lock.parse_pins('package-a>=1.0')


@pytest.mark.parametrize("explicit", [False, True])
def test_pytest_refuses_product_database_before_collection(explicit):
    env = {**os.environ, "DATABASE_URL": "postgresql://product:unused@127.0.0.1:1/networkis"}
    env.pop("ENGINEERING_TEST_DATABASE_URL", None)
    if explicit:
        env["ENGINEERING_TEST_DATABASE_URL"] = env["DATABASE_URL"]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "backend/tests/test_wizard_commands.py"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "product DSNs are forbidden" in result.stderr
    assert "tests collected" not in result.stdout


@pytest.mark.parametrize("status,development,checks", [
    ("PREPARED", True, []),
    ("FAIL", False, []),
    ("PASS", False, [{"name": "typecheck", "exit_code": 0}]),
    ("PASS", True, [{"name": name, "exit_code": 0} for name in
        ("typecheck", "frontend-tests", "backend-tests", "browser-e2e", "small-http", "large-http")]),
    ("PASS", False, [{"name": name, "exit_code": 0} for name in
        ("typecheck", "frontend-tests", "backend-tests", "browser-e2e", "small-http", "large-http")]),
])
def test_deployment_refuses_incomplete_or_development_receipt(tmp_path, status, development, checks):
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"status": status, "development_only": development, "checks": checks}))
    result = subprocess.run(
        [sys.executable, "scripts/deploy-verified-release.py", str(receipt)],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert "Deployment refused" in result.stderr
    # A receipt without image_id could never reach Docker inspection.
    assert "KeyError" not in result.stderr


@pytest.mark.parametrize("changed_input", ["source", "test"])
def test_source_change_during_units_refuses_candidate_build(tmp_path, monkeypatch, changed_input):
    """A green old-source unit run cannot authorize a newer-source image."""
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    for name in ('run-isolated-tests.py', 'write-build-info.py'):
        shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
    source = tmp_path / 'backend' / 'app.py'
    source.parent.mkdir()
    source.write_text('version = 1\n')
    test_source = tmp_path / 'backend' / 'tests' / 'test_example.py'
    test_source.parent.mkdir()
    test_source.write_text('assert True\n')
    spec = importlib.util.spec_from_file_location('release_gate_source_race', ROOT / 'scripts/run-release-gate.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run-release-gate.py', '--output', str(tmp_path / 'reports')])
    monkeypatch.setenv('NIS_TEST_DOCKER', 'docker-must-not-run')
    commands = []

    def completed_units(command, **kwargs):
        commands.append(command)
        if len(commands) == 3:
            if changed_input == 'source':
                source.write_text('version = 2\n')
            else:
                test_source.write_text('assert False\n')
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, 'run', completed_units)
    monkeypatch.setattr(subprocess, 'check_output', lambda *args, **kwargs: pytest.fail('Docker must not execute after changed sources'))
    assert gate.main() == 1
    receipt = json.loads(next((tmp_path / 'reports').glob('*/receipt.json')).read_text())
    assert receipt['status'] == 'FAIL'
    assert ('Sources' if changed_input == 'source' else 'Tests') + ' changed during unit verification' in receipt['error']
    assert [check['name'] for check in receipt['checks']] == ['typecheck', 'frontend-tests', 'backend-tests']
