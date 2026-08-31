"""Small in-process job registry for local simulation runs."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import uuid
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import RUNTIME_ROOT, TRACE_ROOT
from .runtime_config import runtime_settings
from .simulation_service import SimulationService


logger = logging.getLogger(__name__)
MAX_PERSISTED_JOBS = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _job_sort_key(job: dict[str, Any]) -> tuple[str, str]:
    return (
        str(job.get("updated_at") or ""),
        str(job.get("created_at") or ""),
    )


def _compact_result_for_registry(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), list) else []
    compact: dict[str, Any] = {
        key: result[key]
        for key in ("status", "summary", "duration_s", "started_at", "finished_at")
        if key in result
    }
    compact["artifacts"] = artifacts
    compact["artifact_count"] = len(artifacts)
    if set(result) - set(compact):
        compact["registry_truncated"] = True
    return compact


def _compact_job_for_registry(job: dict[str, Any]) -> dict[str, Any]:
    compact = copy.deepcopy(job)
    if "result" in compact:
        compact["result"] = _compact_result_for_registry(compact.get("result"))
    return compact


def _run_simulation_process(
    job_id: str,
    payload: dict[str, Any],
    validate_only: bool,
) -> dict[str, Any]:
    """Run one isolated simulation in a spawned worker process."""
    output_dir = (TRACE_ROOT / job_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return SimulationService().run(payload, output_dir, validate_only=validate_only)


class JobService:
    def __init__(
        self,
        simulation_service: SimulationService | None = None,
        *,
        synchronous: bool | None = None,
        execution_mode: str | None = None,
        max_workers: int | None = None,
        registry_path: Path | None = None,
        persist: bool | None = None,
    ) -> None:
        custom_simulation_service = simulation_service is not None
        self.simulations = simulation_service or SimulationService()
        settings = runtime_settings()
        requested_mode = execution_mode or settings.simulation_executor
        self.execution_mode = "thread" if custom_simulation_service else requested_mode
        self.max_workers = max_workers or settings.simulation_workers
        self.executor: ProcessPoolExecutor | ThreadPoolExecutor | None = None
        # Serverless runtimes may freeze background threads as soon as the HTTP
        # response is returned. Finish the small local simulation before
        # responding there; desktop Flask keeps the asynchronous behavior.
        self.synchronous = bool(os.environ.get("VERCEL")) if synchronous is None else synchronous
        self._jobs: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()
        self.persist = (
            not bool(os.environ.get("PYTEST_CURRENT_TEST")) if persist is None else persist
        )
        self.registry_path = registry_path or RUNTIME_ROOT / "jobs" / "registry.json"
        self._load_registry()

    def _get_executor(self) -> ProcessPoolExecutor | ThreadPoolExecutor:
        if self.executor is None:
            if self.execution_mode == "process":
                self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
            else:
                self.executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="simulation",
                )
        return self.executor

    def _load_registry(self) -> None:
        if not self.persist or not self.registry_path.is_file():
            return
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            for item in jobs:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                job = copy.deepcopy(item)
                if job.get("status") in {"queued", "running"}:
                    job.update(
                        status="failed",
                        error="Simulation wurde durch einen Dienstneustart unterbrochen.",
                        updated_at=_now(),
                    )
                self._jobs[str(job["id"])] = job
            self._prune_locked()
            self._persist_locked()
        except (OSError, ValueError, TypeError):
            logger.exception("Could not load persisted simulation jobs")

    def _prune_locked(self) -> None:
        if len(self._jobs) <= MAX_PERSISTED_JOBS:
            return
        keep = {
            job_id
            for job_id, _job in sorted(
                self._jobs.items(),
                key=lambda item: _job_sort_key(item[1]),
                reverse=True,
            )[:MAX_PERSISTED_JOBS]
        }
        for job_id in list(self._jobs):
            if job_id not in keep and job_id not in self._futures:
                self._jobs.pop(job_id, None)

    def _persist_locked(self) -> None:
        if not self.persist:
            return
        try:
            self._prune_locked()
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.registry_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {"jobs": [_compact_job_for_registry(job) for job in self._jobs.values()]},
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.registry_path)
        except (OSError, TypeError, ValueError):
            logger.exception("Could not persist simulation jobs")

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
            self._persist_locked()
        if self.synchronous:
            self._execute(job_id, copy.deepcopy(payload), validate_only)
            return self.get(job_id) or copy.deepcopy(job)
        if self.execution_mode == "process":
            self._update(job_id, status="running", worker_mode="process")
            self._update_workflow_snapshot(payload, "RUNNING", job_id)
            future = self._get_executor().submit(
                _run_simulation_process,
                job_id,
                copy.deepcopy(payload),
                validate_only,
            )
        else:
            future = self._get_executor().submit(
                self._execute,
                job_id,
                copy.deepcopy(payload),
                validate_only,
            )
        with self._lock:
            self._futures[job_id] = future
        if self.execution_mode == "process":
            future.add_done_callback(
                lambda completed: self._complete_process_job(
                    job_id,
                    payload,
                    validate_only,
                    completed,
                )
            )
        else:
            future.add_done_callback(lambda _completed: self._forget_future(job_id))
        return self.get(job_id) or copy.deepcopy(job)

    def _forget_future(self, job_id: str) -> None:
        with self._lock:
            self._futures.pop(job_id, None)

    def _complete_process_job(
        self,
        job_id: str,
        payload: dict[str, Any],
        validate_only: bool,
        future: Future[Any],
    ) -> None:
        try:
            result = future.result()
            if self._is_cancellation_requested(job_id):
                self._update_workflow_snapshot(payload, "CANCELED", job_id, result=result)
                self._update(job_id, status="canceled", result=result)
                return
            self._record_routing_results(payload, validate_only, job_id, result)
            self._update_workflow_snapshot(payload, "COMPLETED", job_id, result=result)
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            logger.exception("Simulation worker failed")
            self._update_workflow_snapshot(payload, "FAILED", job_id)
            self._update(job_id, status="failed", error=str(exc))
        finally:
            with self._lock:
                self._futures.pop(job_id, None)

    def _execute(self, job_id: str, payload: dict[str, Any], validate_only: bool) -> None:
        if self._is_cancellation_requested(job_id):
            self._update_workflow_snapshot(payload, "CANCELED", job_id)
            self._update(job_id, status="canceled")
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
                self._update_workflow_snapshot(payload, "CANCELED", job_id, result=result)
                self._update(job_id, status="canceled", result=result)
                return
            self._record_routing_results(payload, validate_only, job_id, result)
            self._update_workflow_snapshot(payload, "COMPLETED", job_id, result=result)
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            self._update_workflow_snapshot(payload, "FAILED", job_id)
            self._update(job_id, status="failed", error=str(exc))

    @staticmethod
    def _record_routing_results(
        payload: dict[str, Any],
        validate_only: bool,
        job_id: str,
        result: dict[str, Any],
    ) -> None:
        config = payload.get("config") if isinstance(payload.get("config"), dict) else payload
        routing_entry_ids = config.get("routing_entry_ids", []) if isinstance(config, dict) else []
        if not routing_entry_ids or validate_only:
            return
        try:
            from ..engineering.routing.repository import record_simulation_results

            record_simulation_results(
                [str(route_id) for route_id in routing_entry_ids], job_id, result
            )
        except Exception:
            # A completed simulation remains valid even if optional engineering
            # observations cannot be persisted temporarily.
            logger.exception("Could not persist routing simulation observations")

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
            self._persist_locked()

    def _is_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._jobs.get(job_id, {}).get("cancellation_requested"))

    def cancel(self, job_id: str, project_id: str | None = None) -> dict[str, Any] | None:
        canceled_before_start = False
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or (project_id is not None and job.get("project_id") != project_id):
                return None
            if job["status"] in {"completed", "failed", "canceled"}:
                return copy.deepcopy(job)
            job["cancellation_requested"] = True
            job["updated_at"] = _now()
            future = self._futures.get(job_id)
            if future is not None and future.cancel():
                job["status"] = "canceled"
                canceled_before_start = True
            self._persist_locked()
            response = copy.deepcopy(job)
        if canceled_before_start:
            self._update_workflow_snapshot(response, "CANCELED", job_id)
        return response

    def get(self, job_id: str, project_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or (project_id is not None and job.get("project_id") != project_id):
                return None
            return copy.deepcopy(job)

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [
                _compact_job_for_registry(job)
                for job in sorted(
                    (
                        job for job in self._jobs.values()
                        if project_id is None or job.get("project_id") == project_id
                    ),
                    key=lambda item: item["created_at"],
                    reverse=True,
                )
            ]

    def artifact(self, job_id: str, artifact_index: int, project_id: str | None = None) -> Path | None:
        job = self.get(job_id, project_id)
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

    def runtime_summary(self) -> dict[str, Any]:
        with self._lock:
            active = sum(
                job.get("status") in {"queued", "running"}
                for job in self._jobs.values()
            )
        return {
            "executor": "synchronous" if self.synchronous else self.execution_mode,
            "max_workers": 0 if self.synchronous else self.max_workers,
            "active_jobs": active,
            "persisted": self.persist,
        }

    def shutdown(self) -> None:
        if self.executor is not None:
            self.executor.shutdown(wait=False, cancel_futures=True)


JOBS = JobService()
