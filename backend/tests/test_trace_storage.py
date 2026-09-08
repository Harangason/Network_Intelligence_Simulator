import importlib
from concurrent.futures import Future
from pathlib import Path

import pytest

from backend.app import create_app
from backend.app.job_service import JobService, _run_simulation_process
from backend.app.trace_storage import TraceStorage, StorageError, StorageUnavailable


@pytest.fixture
def storage(tmp_path):
    return TraceStorage(default_root=tmp_path / "default", settings_path=tmp_path / "settings.json", container=False, host_path="")


class TinySimulation:
    def run(self, payload, output_dir, *, validate_only=False):
        path = output_dir / "universal_trace.jsonl"
        path.write_text('{"time_s":0,"signals":[]}\n', encoding="utf-8")
        return {"status": "completed", "artifacts": [str(path)]}


def test_settings_are_persistent_project_scoped_and_reset_does_not_delete(storage, tmp_path):
    selected = tmp_path / "Meine Traces ä"
    check = storage.validate(str(selected))
    assert not check["exists"] and not selected.exists() and check["free_bytes"] > 0
    saved = storage.save("20260908103453543-44dfbb43", str(selected))
    assert saved["path"] == str(selected)
    restored = TraceStorage(default_root=storage.default_root, settings_path=storage.settings_path, container=False)
    assert restored.root_for("network-project-20260908103453543-44dfbb43") == selected
    assert restored.root_for("other") == storage.default_root
    (selected / "keep.txt").write_text("keep")
    assert storage.save("20260908103453543-44dfbb43", None)["is_default"]
    assert (selected / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize("bad", ["", "relative/path", "../escape", 42, [], "bad\x00path"])
def test_invalid_paths_leave_setting_unchanged(storage, tmp_path, bad):
    before = storage.save("p", str(tmp_path / "good"))
    with pytest.raises(StorageError):
        storage.save("p", bad)
    assert storage.settings("p") == before


def test_file_and_unwritable_paths_do_not_silently_fallback(storage, tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_text("keep")
    with pytest.raises(StorageError):
        storage.validate(str(file))
    def denied(*args, **kwargs):
        raise PermissionError("read only")
    monkeypatch.setattr("backend.app.trace_storage.tempfile.TemporaryFile", denied)
    with pytest.raises(StorageUnavailable):
        storage.save("p", str(tmp_path / "unwritable"))
    assert storage.settings("p")["is_default"]
    with pytest.raises(StorageUnavailable):
        JobService(storage=storage, persist=False).submit({"project_id": "p"})


def test_corrupt_settings_fail_closed(storage):
    storage.settings_path.write_text("{invalid")
    with pytest.raises(StorageUnavailable):
        storage.settings("p")
    with pytest.raises(StorageUnavailable):
        storage.save("p", None)
    assert storage.settings_path.read_text() == "{invalid"


def test_docker_mapping_browse_and_escape_protection(tmp_path):
    mount = tmp_path / "mounted"
    mount.mkdir()
    (mount / "Messung ä").mkdir()
    service = TraceStorage(default_root=tmp_path / "default", settings_path=tmp_path / "settings.json",
                           container=True, host_path="D:/Meine Traces", mount_path=mount)
    assert service.resolve("d:\\meine traces\\Messung ä") == mount / "Messung ä"
    assert service.save("p", "D:/Meine Traces/Messung ä")["path"] == "D:\\Meine Traces\\Messung ä"
    assert service.directories("p", "D:/Meine Traces")["parent"] is None
    assert service.directories("p", "D:/Meine Traces")["directories"] == [
        {"name": "Messung ä", "path": "D:\\Meine Traces\\Messung ä"}]
    for bad in ["E:/not-mounted", str(tmp_path / "elsewhere"), "D:/Meine Traces/../escape"]:
        with pytest.raises(StorageError):
            service.save("p", bad)


def test_jobs_capture_path_and_old_downloads_survive_change_and_restart(storage, tmp_path):
    selected = tmp_path / "selected"
    storage.save("p", str(selected))
    registry = tmp_path / "registry.json"
    jobs = JobService(TinySimulation(), storage=storage, synchronous=True, registry_path=registry, persist=True)
    first = jobs.submit({"project_id": "p", "output_dir": str(tmp_path / "payload-must-not-win")})
    assert first["status"] == "completed"
    assert Path(first["output_dir"]).parent == selected
    artifact = jobs.artifact(first["id"], 0, "p")
    assert artifact.is_file()
    storage.save("p", None)
    second = jobs.submit({"project_id": "p"})
    assert Path(second["output_dir"]).parent == storage.default_root
    restored = JobService(storage=storage, registry_path=registry, persist=True)
    assert restored.artifact(first["id"], 0, "p") == artifact
    assert restored.artifact(first["id"], 0, "other") is None
    assert restored.artifact(first["id"], -1, "p") is None
    restored._jobs[first["id"]]["result"]["artifacts"] = [str(storage.settings_path)]
    assert restored.artifact(first["id"], 0, "p") is None


@pytest.mark.parametrize("mode", ["thread", "process"])
def test_queued_worker_keeps_captured_path_after_setting_change(storage, tmp_path, monkeypatch, mode):
    calls = []
    class Executor:
        def submit(self, *args):
            calls.append(args)
            return Future()
    monkeypatch.setattr("backend.app.job_service.SimulationService", TinySimulation)
    selected = tmp_path / "selected"
    storage.save("p", str(selected))
    jobs = JobService(storage=storage, synchronous=False, execution_mode=mode, persist=False)
    monkeypatch.setattr(jobs, "_get_executor", lambda: Executor())
    job = jobs.submit({"project_id": "p"})
    storage.save("p", None)
    function, *args = calls[0]
    result = function(*args)
    if mode == "process":
        assert function is _run_simulation_process
        future = Future()
        future.set_result(result)
        jobs._complete_process_job(job["id"], {"project_id": "p"}, False, future)
    assert Path(jobs.get(job["id"])["output_dir"]).parent == selected
    assert jobs.artifact(job["id"], 0, "p").is_file()


def test_storage_http_contract_and_trace_download_after_path_change(storage, tmp_path, monkeypatch):
    api = importlib.import_module("backend.app.api")
    jobs = JobService(TinySimulation(), storage=storage, synchronous=True, persist=False)
    monkeypatch.setattr(api, "JOBS", jobs)
    client = create_app(testing=True).test_client()
    headers = {"X-Project-ID": "p", "X-NetworkIS-Storage": "confirmed"}
    target = str(tmp_path / "http traces")
    assert client.put("/api/storage/settings", json={"path": target}).status_code == 403
    assert client.put("/api/storage/settings", json={}, headers=headers).status_code == 400
    assert client.post("/api/storage/validate", json={"path": target}, headers=headers).status_code == 200
    assert client.put("/api/storage/settings", json={"path": target}, headers=headers).status_code == 200
    assert client.get("/api/storage/settings", headers=headers).get_json()["path"] == target
    assert client.get("/api/storage/settings", headers={"X-Project-ID": "other"}).get_json()["is_default"]
    assert client.get("/api/storage/directories", headers=headers).status_code == 200
    job = client.post("/api/simulations", json={"project_id": "p"}, headers=headers).get_json()
    assert job["status"] == "completed"
    assert client.put("/api/storage/settings", json={"path": None}, headers=headers).status_code == 200
    assert client.get(f'/api/simulations/{job["id"]}/artifacts/0', headers=headers).status_code == 200
    assert client.get(f'/api/simulations/{job["id"]}/trace-window', headers=headers).get_json()["count"] == 1
    response = client.options("/api/storage/settings", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Headers": "X-NetworkIS-Storage"})
    assert "X-NetworkIS-Storage" not in response.headers.get("Access-Control-Allow-Headers", "")


def test_storage_http_reports_io_failure(storage, monkeypatch):
    api = importlib.import_module("backend.app.api")
    monkeypatch.setattr(api, "JOBS", JobService(storage=storage, persist=False))
    def unavailable(*args, **kwargs):
        raise StorageUnavailable("Speicher nicht erreichbar")
    monkeypatch.setattr(storage, "root_for", unavailable)
    client = create_app(testing=True).test_client()
    assert client.get("/api/storage/settings").status_code == 503
    assert client.post("/api/simulations", json={"project_id": "p"}).status_code == 503
