from pathlib import Path

from backend.app.job_service import JobService


def test_vercel_jobs_run_synchronously(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    service = JobService()
    calls: list[tuple[str, dict, bool]] = []

    def execute(job_id: str, payload: dict, validate_only: bool) -> None:
        calls.append((job_id, payload, validate_only))
        service._update(job_id, status="completed", result={"status": "completed"})

    monkeypatch.setattr(service, "_execute", execute)
    job = service.submit({"technology": "can_fd"})

    assert calls == [(job["id"], {"technology": "can_fd"}, False)]
    assert job["status"] == "completed"


def test_desktop_jobs_default_to_process_workers(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    service = JobService(
        synchronous=False,
        execution_mode="process",
        max_workers=6,
        persist=False,
    )

    assert service.runtime_summary() == {
        "executor": "process",
        "max_workers": 6,
        "active_jobs": 0,
        "persisted": False,
    }


def test_job_registry_survives_restart(tmp_path: Path) -> None:
    registry = tmp_path / "jobs" / "registry.json"
    first = JobService(synchronous=True, registry_path=registry, persist=True)
    first._jobs["interrupted"] = {
        "id": "interrupted",
        "status": "running",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with first._lock:
        first._persist_locked()

    restored = JobService(synchronous=True, registry_path=registry, persist=True)

    assert restored.get("interrupted")["status"] == "failed"
    assert "Dienstneustart" in restored.get("interrupted")["error"]


def test_jobs_are_isolated_by_project() -> None:
    service = JobService(synchronous=True, persist=False)
    service._jobs = {
        "project-a-job": {
            "id": "project-a-job",
            "project_id": "project-a",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00Z",
            "result": {"artifacts": []},
        },
        "project-b-job": {
            "id": "project-b-job",
            "project_id": "project-b",
            "status": "completed",
            "created_at": "2026-01-02T00:00:00Z",
            "result": {"artifacts": []},
        },
    }

    assert [job["id"] for job in service.list("project-a")] == ["project-a-job"]
    assert service.get("project-b-job", "project-a") is None
    assert service.cancel("project-b-job", "project-a") is None
    assert service.artifact("project-b-job", 0, "project-a") is None
    assert service.get("project-b-job", "project-b")["id"] == "project-b-job"


def test_terminal_job_status_is_published_after_workflow_snapshot(monkeypatch, tmp_path: Path) -> None:
    class SimulationStub:
        @staticmethod
        def run(_payload: dict, _output_dir: Path, *, validate_only: bool) -> dict:
            assert validate_only is False
            return {"status": "completed"}

    service = JobService(
        simulation_service=SimulationStub(),
        synchronous=True,
        persist=False,
    )
    service._jobs["job-1"] = {
        "id": "job-1",
        "project_id": "project-1",
        "status": "queued",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    events: list[tuple[str, str]] = []
    original_update = service._update

    monkeypatch.setattr("backend.app.job_service.TRACE_ROOT", tmp_path)
    monkeypatch.setattr(service, "_record_routing_results", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "_update_workflow_snapshot",
        lambda _payload, status, _job_id, **_kwargs: events.append(("workflow", status)),
    )

    def record_job_update(job_id: str, **changes) -> None:
        original_update(job_id, **changes)
        events.append(("job", str(changes.get("status"))))

    monkeypatch.setattr(service, "_update", record_job_update)
    service._execute(
        "job-1",
        {"project_id": "project-1", "workflow_snapshot_id": "snapshot-1"},
        False,
    )

    assert events[-2:] == [("workflow", "COMPLETED"), ("job", "completed")]
