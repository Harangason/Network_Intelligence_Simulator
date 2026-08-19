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
