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


def test_volume_rebase_requires_existing_destination(tmp_path, monkeypatch):
    from backend.nis.infrastructure import paths
    monkeypatch.setenv("NIS_LEGACY_DATA_ROOT", str(tmp_path / "old"))
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "data")
    (tmp_path / "data/traces/job").mkdir(parents=True)
    old = str(tmp_path / "old/traces/job")
    assert paths.migrated_data_path(old) == str(tmp_path / "data/traces/job")
    missing = str(tmp_path / "old/missing")
    assert paths.migrated_data_path(missing) == missing
    unrelated = str(tmp_path / "other/job")
    assert paths.migrated_data_path(unrelated) == unrelated
