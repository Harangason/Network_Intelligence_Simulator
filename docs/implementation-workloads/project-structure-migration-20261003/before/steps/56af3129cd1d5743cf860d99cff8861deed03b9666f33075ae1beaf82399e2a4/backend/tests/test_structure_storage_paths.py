"""Migration storage contracts: stable roots and legacy isolation compatibility."""
from backend.nis.infrastructure.paths import storage_paths_for


def test_defaults_do_not_depend_on_launch_directory(tmp_path, monkeypatch):
    backend = tmp_path / "checkout/backend"
    other = tmp_path / "elsewhere"
    other.mkdir()
    before = storage_paths_for(backend, {})
    monkeypatch.chdir(other)
    assert storage_paths_for(backend, {}) == before
    assert before.data == tmp_path / "checkout/var/data"
    assert before.runtime == tmp_path / "checkout/var/runtime"
    assert before.artifacts == tmp_path / "checkout/artifacts"


def test_explicit_roots_override_legacy_without_mixing_classes(tmp_path):
    roots = storage_paths_for(tmp_path / "backend", {
        "SIMULATOR_RUNTIME_ROOT": str(tmp_path / "old"),
        "NIS_DATA_DIR": "durable", "NIS_RUNTIME_DIR": "temporary",
        "NIS_ARTIFACTS_DIR": "results",
    })
    assert roots.data == tmp_path / "durable"
    assert roots.runtime == tmp_path / "temporary"
    assert roots.artifacts == tmp_path / "results"


def test_legacy_test_root_keeps_all_test_writes_isolated(tmp_path):
    roots = storage_paths_for(tmp_path / "backend", {"SIMULATOR_RUNTIME_ROOT": str(tmp_path / "test")})
    assert roots.runtime == roots.data == tmp_path / "test"


def test_vercel_has_writable_ephemeral_defaults(tmp_path):
    roots = storage_paths_for(tmp_path / "backend", {"VERCEL": "1"})
    assert "communication-simulator" in str(roots.runtime)
    assert roots.data == roots.runtime / "data"
