"""Small in-process job registry for local simulation runs."""

from __future__ import annotations

import copy
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TRACE_ROOT
from .simulation_service import SimulationService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JobService:
    def __init__(self, simulation_service: SimulationService | None = None) -> None:
        self.simulations = simulation_service or SimulationService()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="simulation")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, payload: dict[str, Any], *, validate_only: bool = False) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "status": "queued",
            "validate_only": validate_only,
            "created_at": _now(),
            "updated_at": _now(),
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self.executor.submit(self._execute, job_id, copy.deepcopy(payload), validate_only)
        return copy.deepcopy(job)

    def _execute(self, job_id: str, payload: dict[str, Any], validate_only: bool) -> None:
        self._update(job_id, status="running")
        try:
            output_dir = (TRACE_ROOT / job_id).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            result = self.simulations.run(
                payload,
                output_dir,
                validate_only=validate_only,
            )
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)
            self._jobs[job_id]["updated_at"] = _now()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(job)
                for job in sorted(
                    self._jobs.values(),
                    key=lambda item: item["created_at"],
                    reverse=True,
                )
            ]

    def artifact(self, job_id: str, artifact_index: int) -> Path | None:
        job = self.get(job_id)
        if not job or not job.get("result"):
            return None
        artifacts = job["result"].get("artifacts") or []
        if artifact_index < 0 or artifact_index >= len(artifacts):
            return None
        candidate = Path(artifacts[artifact_index]).resolve()
        allowed_root = (TRACE_ROOT / job_id).resolve()
        if candidate != allowed_root and allowed_root not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None


JOBS = JobService()
