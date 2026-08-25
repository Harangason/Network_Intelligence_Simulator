"""Small in-process job registry for local simulation runs."""

from __future__ import annotations

import copy
import logging
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TRACE_ROOT
from .simulation_service import SimulationService


logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JobService:
    def __init__(
        self,
        simulation_service: SimulationService | None = None,
        *,
        synchronous: bool | None = None,
    ) -> None:
        self.simulations = simulation_service or SimulationService()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="simulation")
        # Serverless runtimes may freeze background threads as soon as the HTTP
        # response is returned. Finish the small local simulation before
        # responding there; desktop Flask keeps the asynchronous behavior.
        self.synchronous = bool(os.environ.get("VERCEL")) if synchronous is None else synchronous
        self._jobs: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future[Any]] = {}
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
            "project_id": str(payload.get("project_id") or "default"),
            "workflow_snapshot_id": payload.get("workflow_snapshot_id"),
        }
        with self._lock:
            self._jobs[job_id] = job
        if self.synchronous:
            self._execute(job_id, copy.deepcopy(payload), validate_only)
            return self.get(job_id) or copy.deepcopy(job)
        future = self.executor.submit(self._execute, job_id, copy.deepcopy(payload), validate_only)
        with self._lock:
            self._futures[job_id] = future
        return copy.deepcopy(job)

    def _execute(self, job_id: str, payload: dict[str, Any], validate_only: bool) -> None:
        if self._is_cancellation_requested(job_id):
            self._update(job_id, status="canceled")
            self._update_workflow_snapshot(payload, "CANCELED", job_id)
            return
        self._update(job_id, status="running")
        self._update_workflow_snapshot(payload, "RUNNING", job_id)
        try:
            output_dir = (TRACE_ROOT / job_id).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            result = self.simulations.run(
                payload,
                output_dir,
                validate_only=validate_only,
            )
            if self._is_cancellation_requested(job_id):
                self._update(job_id, status="canceled", result=result)
                self._update_workflow_snapshot(payload, "CANCELED", job_id, result=result)
                return
            config = payload.get("config") if isinstance(payload.get("config"), dict) else payload
            routing_entry_ids = config.get("routing_entry_ids", []) if isinstance(config, dict) else []
            if routing_entry_ids and not validate_only:
                try:
                    from ..engineering.routing.repository import record_simulation_results

                    record_simulation_results(
                        [str(route_id) for route_id in routing_entry_ids], job_id, result
                    )
                except Exception:
                    # A completed simulation remains valid even if optional engineering
                    # observations cannot be persisted temporarily.
                    logger.exception("Could not persist routing simulation observations")
            self._update(job_id, status="completed", result=result)
            self._update_workflow_snapshot(payload, "COMPLETED", job_id, result=result)
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))
            self._update_workflow_snapshot(payload, "FAILED", job_id)

    @staticmethod
    def _update_workflow_snapshot(
        payload: dict[str, Any],
        status: str,
        job_id: str,
        *,
        result: dict[str, Any] | None = None,
    ) -> None:
        snapshot_id = payload.get("workflow_snapshot_id")
        if not snapshot_id:
            return
        try:
            from ..engineering.workflow.service import WorkflowStatusService

            WorkflowStatusService(str(payload.get("project_id") or "default")).update_simulation_snapshot(
                str(snapshot_id), status=status, job_id=job_id, result=result
            )
        except Exception:
            logger.exception("Could not update workflow simulation snapshot")

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)
            self._jobs[job_id]["updated_at"] = _now()

    def _is_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._jobs.get(job_id, {}).get("cancellation_requested"))

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        canceled_before_start = False
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] in {"completed", "failed", "canceled"}:
                return copy.deepcopy(job)
            job["cancellation_requested"] = True
            job["updated_at"] = _now()
            future = self._futures.get(job_id)
            if future is not None and future.cancel():
                job["status"] = "canceled"
                canceled_before_start = True
            response = copy.deepcopy(job)
        if canceled_before_start:
            self._update_workflow_snapshot(response, "CANCELED", job_id)
        return response

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
