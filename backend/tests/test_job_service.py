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
