"""Small in-process job registry for local simulation runs."""

from __future__ import annotations

import copy
import json
import logging
import multiprocessing
import os
import tempfile
import threading
import uuid
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import RUNTIME_ROOT, TRACE_ROOT
from .runtime_config import runtime_settings
from .simulation_service import SimulationService
from .trace_storage import TraceStorage
from simulation_cancellation import cancellation_requested, cancellation_scope, request_cancellation


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
    # Discard heavy traces before copying while holding the registry lock.
    # List and persistence callers still receive an independent metadata tree.
    compact = {key: value for key, value in job.items() if key != "result"}
    if "result" in job:
        compact["result"] = _compact_result_for_registry(job.get("result"))
    return copy.deepcopy(compact)


def _fallback_registry_path() -> Path:
    instance = os.environ.get("SIMULATOR_INSTANCE_ID", "local").strip() or "local"
    safe_instance = "".join(character for character in instance if character.isalnum())[:8] or "local"
    return Path(tempfile.gettempdir()) / "networkis-runtime" / "jobs" / f"registry-{safe_instance}.json"


def _run_simulation_process(
    job_id: str,
    payload: dict[str, Any],
    validate_only: bool,
    output_directory: str | None = None,
) -> dict[str, Any]:
    """Run one isolated simulation in a spawned worker process."""
    output_dir = Path(output_directory).resolve() if output_directory else (TRACE_ROOT / job_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with cancellation_scope(output_dir):
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
        storage: TraceStorage | None = None,
    ) -> None:
        self._storage = storage
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
        self._uses_fallback_registry = False
        self._load_registry()

    def _get_executor(self) -> ProcessPoolExecutor | ThreadPoolExecutor:
        if self.executor is None:
            if self.execution_mode == "process":
                # A forked worker inherits psycopg sockets and prepared-statement
                # state from the Flask process. Spawning gives simulations a clean
                # interpreter and keeps the parent's connection pool intact.
                self.executor = ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=multiprocessing.get_context("spawn"),
                )
            else:
                self.executor = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="simulation",
                )
        return self.executor

    def _load_registry(self) -> None:
        if not self.persist:
            return
        try:
            if not self.registry_path.is_file():
                return
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            for item in jobs:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                job = copy.deepcopy(item)
                if job.get("status") in {"queued", "running"}:
                    canceled = bool(job.get('cancellation_requested')) or cancellation_requested(
                        job.get('output_dir') or TRACE_ROOT / str(job['id']))
                    job.update(
                        status="canceled" if canceled else "failed",
                        error=None if canceled else "Simulation wurde durch einen Dienstneustart unterbrochen.",
                        cancellation_requested=canceled,
                        recovery_pending=bool(job.get('workflow_snapshot_id')),
                        updated_at=_now(),
                    )
                self._jobs[str(job["id"])] = job
            self._prune_locked()
            self._persist_locked()
        except PermissionError:
            if self._switch_to_fallback_registry():
                self._load_registry()
            else:
                logger.exception("Could not load persisted simulation jobs")
        except (OSError, ValueError, TypeError):
            logger.exception("Could not load persisted simulation jobs")

    def _switch_to_fallback_registry(self) -> bool:
        if self._uses_fallback_registry:
            return False
        fallback = _fallback_registry_path()
        if fallback == self.registry_path:
            return False
        logger.warning("Simulation job registry is not writable, using fallback %s", fallback)
        self.registry_path = fallback
        self._uses_fallback_registry = True
        return True

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
        except PermissionError:
            if self._switch_to_fallback_registry():
                self._persist_locked()
            else:
                logger.exception("Could not persist simulation jobs")
        except (OSError, TypeError, ValueError):
            logger.exception("Could not persist simulation jobs")

    @property
    def storage(self) -> TraceStorage:
        return self._storage or TraceStorage()

    def submit(self, payload: dict[str, Any], *, validate_only: bool = False) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        output_dir = self.storage.output_for(payload.get("project_id") or "default", job_id)
        job = {
            "id": job_id,
            "output_dir": str(output_dir),
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
        return self._schedule(job_id, payload, validate_only)

    def recover_interrupted(self) -> int:
        """Resume only previously claimed, current workflow snapshots.

        Keep the job identity and frozen configuration. Partial output remains
        in its old directory; the next attempt writes an independent directory.
        A completed snapshot reconciles a lost final registry write without
        executing the simulation twice.
        """
        from ..engineering.workflow.service import WorkflowStatusService
        with self._lock:
            candidates = [copy.deepcopy(job) for job in self._jobs.values()
                          if job.get('recovery_pending') or
                          (job.get('cancellation_requested') and job.get('workflow_snapshot_id'))]
        recovered = 0
        for candidate in candidates:
            job_id = candidate['id']
            try:
                # A crash can occur after the durable marker but before the
                # registry/snapshot write. Never escape that canceled attempt
                # by giving its recovery a fresh directory without the marker.
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job:
                        continue
                    canceled = bool(job.get('cancellation_requested')) or cancellation_requested(
                        job.get('output_dir') or TRACE_ROOT / job_id)
                    if canceled:
                        job.update(status='canceled', cancellation_requested=True,
                                   recovery_pending=False, error=None, updated_at=_now())
                        self._persist_locked()
                if canceled:
                    self._update_workflow_snapshot(candidate, 'CANCELED', job_id)
                    continue
                snapshot = WorkflowStatusService(candidate['project_id']).get_simulation_snapshot(
                    str(candidate['workflow_snapshot_id']), require_current=True)
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job or not job.get('recovery_pending') or job.get('cancellation_requested'):
                        continue
                    if (not snapshot or snapshot.get('is_outdated')
                            or snapshot.get('job_id') not in {None, job_id}
                            or snapshot.get('status') not in {'RUNNING', 'COMPLETED'}
                            or (snapshot.get('status') == 'COMPLETED' and not isinstance(snapshot.get('result'), dict))
                            or (snapshot.get('status') == 'RUNNING' and not isinstance(snapshot.get('configuration'), dict))):
                        job.update(recovery_pending=False, status='canceled' if snapshot and snapshot.get('status') == 'CANCELED' else 'failed',
                                   error='Unterbrochene Simulation benÃ¶tigt einen aktuellen, freigegebenen Snapshot.', updated_at=_now())
                        self._persist_locked()
                        continue
                    if snapshot['status'] == 'COMPLETED':
                        job.update(recovery_pending=False, status='completed', result=snapshot.get('result'), error=None, updated_at=_now())
                        self._persist_locked()
                        recovered += 1
                        continue
                    old_output = str(job['output_dir'])
                    attempt = int(job.get('recovery_count') or 0) + 1
                    base_output = job.get('original_output_dir') or old_output
                    job.update(status='queued', error=None, result=None, recovery_pending=False,
                               recovery_count=attempt, original_output_dir=base_output,
                               interrupted_outputs=[*(job.get('interrupted_outputs') or []), old_output],
                               output_dir=str(Path(base_output) / f'recovery-{attempt}'), updated_at=_now())
                    self._persist_locked()
                payload = {'project_id': candidate['project_id'], 'workflow_snapshot_id': candidate['workflow_snapshot_id'],
                           'workflow_managed': True, 'config': snapshot['configuration']}
                self._schedule(job_id, payload, bool(candidate.get('validate_only')))
                recovered += 1
            except Exception:
                logger.exception('Interrupted simulation %s could not be recovered', job_id)
        return recovered

    def _schedule(self, job_id: str, payload: dict[str, Any], validate_only: bool) -> dict[str, Any]:
        # Attempt directories are not logical identities. Always set this at the
        # trusted submission boundary, including normal jobs and every recovery.
        payload = {**copy.deepcopy(payload), 'simulation_job_id': job_id}
        job = self.get(job_id) or {}
        output_dir = Path(job['output_dir'])
        if self.synchronous:
            self._execute(job_id, copy.deepcopy(payload), validate_only)
            return self.get(job_id) or copy.deepcopy(job)
        try:
            if self.execution_mode == "process":
                self._update(job_id, status="running", worker_mode="process")
                self._update_workflow_snapshot(payload, "RUNNING", job_id)
                future = self._get_executor().submit(
                    _run_simulation_process,
                    job_id,
                    copy.deepcopy(payload),
                    validate_only,
                    str(output_dir),
                )
            else:
                future = self._get_executor().submit(
                    self._execute,
                    job_id,
                    copy.deepcopy(payload),
                    validate_only,
                )
        except Exception as error:
            # Only a failed submission is retryable here. After submit returns,
            # a worker may already be executing even if later bookkeeping fails.
            with self._lock:
                current = self._jobs.get(job_id)
                if current and not current.get('cancellation_requested') and current.get('status') != 'canceled':
                    current.update(status='failed', error=str(error),
                                   recovery_pending=bool(current.get('recovery_count')), updated_at=_now())
                    self._persist_locked()
                    failed_initial = not current.get('recovery_pending')
                else:
                    failed_initial = False
            if failed_initial:
                self._update_workflow_snapshot(payload, 'FAILED', job_id)
            raise
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
            if self._is_cancellation_requested(job_id) or self._status(job_id) == "canceled":
                return
            self._record_routing_results(payload, validate_only, job_id, result)
            self._update_workflow_snapshot(payload, "COMPLETED", job_id, result=result)
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            if self._status(job_id) == "canceled":
                return
            logger.exception("Simulation worker failed")
            self._update_workflow_snapshot(payload, "FAILED", job_id)
            self._update(job_id, status="failed", error=str(exc))
        finally:
            with self._lock:
                self._futures.pop(job_id, None)

    def _execute(self, job_id: str, payload: dict[str, Any], validate_only: bool) -> None:
        if self._is_cancellation_requested(job_id) or self._status(job_id) == "canceled":
            self._update_workflow_snapshot(payload, "CANCELED", job_id)
            self._update(job_id, status="canceled")
            return
        self._update(job_id, status="running")
        self._update_workflow_snapshot(payload, "RUNNING", job_id)
        try:
            job = self.get(job_id) or {}
            output_dir = Path(job.get("output_dir") or TRACE_ROOT / job_id).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            with cancellation_scope(output_dir):
                result = self.simulations.run(
                    payload,
                    output_dir,
                    validate_only=validate_only,
                )
            if self._is_cancellation_requested(job_id) or self._status(job_id) == "canceled":
                return
            self._record_routing_results(payload, validate_only, job_id, result)
            self._update_workflow_snapshot(payload, "COMPLETED", job_id, result=result)
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            if self._status(job_id) == "canceled":
                return
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
            from ..engineering.project_context import activate_project, reset_project
            from ..engineering.routing.repository import record_simulation_results

            # Executor threads and process completion callbacks do not inherit
            # the submitting request's ContextVar. Bind the trusted job owner
            # for this write, then restore the caller's context on every path.
            token = activate_project(payload.get("project_id") or "default")
            try:
                record_simulation_results(
                    [str(route_id) for route_id in routing_entry_ids], job_id, result
                )
            finally:
                reset_project(token)
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
            job = self._jobs[job_id]
            if (job.get('status') == 'canceled' or job.get('cancellation_requested')) and values.get('status') in {
                'queued', 'running', 'completed', 'failed'
            }:
                return
            job.update(values)
            job["updated_at"] = _now()
            self._persist_locked()

    def _is_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._jobs.get(job_id, {}).get("cancellation_requested"))

    def _status(self, job_id: str) -> str | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return str(job.get("status")) if job else None

    def cancel(self, job_id: str, project_id: str | None = None) -> dict[str, Any] | None:
        canceled = False
        future: Future[Any] | None = None
        workflow_payload: dict[str, Any] | None = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or (project_id is not None and job.get("project_id") != project_id):
                return None
            if job["status"] in {"completed", "failed", "canceled"}:
                return copy.deepcopy(job)
            # Future.cancel only stops queued work. The attempt-local marker
            # also reaches an already running thread or spawned process.
            request_cancellation(job.get('output_dir') or TRACE_ROOT / job_id)
            job["cancellation_requested"] = True
            job["status"] = "canceled"
            job["canceled_at"] = _now()
            job["error"] = None
            job["updated_at"] = _now()
            future = self._futures.get(job_id)
            self._persist_locked()
            response = copy.deepcopy(job)
            workflow_payload = response
            canceled = True
        # Future.cancel invokes done callbacks synchronously. Those callbacks
        # inspect/update this registry and therefore must run outside its lock.
        if canceled and future is not None:
            future.cancel()
        if canceled and workflow_payload is not None:
            self._update_workflow_snapshot(workflow_payload, "CANCELED", job_id)
        return response

    def get(self, job_id: str, project_id: str | None = None, *, metadata: bool = False) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or (project_id is not None and job.get("project_id") != project_id):
                return None
            if metadata:
                return copy.deepcopy({**{k: v for k, v in job.items() if k != "result"},
                                      "result": _compact_result_for_registry(job.get("result"))})
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

    def forget_project(self, project_id: str) -> None:
        with self._lock:
            matching = [key for key, job in self._jobs.items() if job.get('project_id') == project_id]
            if any(self._jobs[key].get('status') not in {'completed', 'failed', 'canceled'} for key in matching):
                raise ValueError('FÃ¼r dieses Projekt lÃ¤uft noch eine Simulation.')
            for key in matching:
                self._jobs.pop(key, None)
            self._persist_locked()

    def artifact(self, job_id: str, artifact_index: int, project_id: str | None = None) -> Path | None:
        job = self.get(job_id, project_id, metadata=True)
        if not job or not job.get("result"):
            return None
        artifacts = job["result"].get("artifacts") or []
        if artifact_index < 0 or artifact_index >= len(artifacts):
            return None
        candidate = Path(artifacts[artifact_index]).resolve()
        allowed_root = Path(job.get("output_dir") or TRACE_ROOT / job_id).resolve()
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


# Spawn imports this module before executing the submitted worker function.
# Only the application process owns the shared registry; importing a worker
# must not rewrite its parent's queued/running jobs as interrupted.
JOBS = JobService(persist=None if multiprocessing.current_process().name == 'MainProcess' else False)
