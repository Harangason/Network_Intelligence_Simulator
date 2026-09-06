"""Persistent wizard execution status for connection-independent agent runs."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..project_context import activate_project, reset_project
from ..workflow.service import WorkflowStatusService
from ..workflow.models import WORKFLOW_STEPS


WIZARD_RUN_PATTERN = re.compile(r"\bLauf-ID:\s*([A-Za-z0-9._-]{8,120})", re.IGNORECASE)
TERMINAL_SUCCESS = {"COMPLETED"}
TERMINAL_REVIEW = {"READY_FOR_REVIEW", "REVIEW_REQUIRED", "VALIDATED", "PROPOSED"}


def extract_wizard_run_id(prompt: str) -> str | None:
    match = WIZARD_RUN_PATTERN.search(prompt or "")
    return match.group(1).rstrip(".") if match else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def execution_step(summary: dict) -> str:
    """A continuation cannot reset an already completed artifact's progress."""
    active = summary.get('active_step') or 'engineering_model'
    statuses = summary.get('statuses') or {}
    done = {'COMPLETE', 'APPROVED', 'WARNING'}
    if active in WORKFLOW_STEPS and statuses.get(active) in done:
        return next((step for step in WORKFLOW_STEPS[WORKFLOW_STEPS.index(active) + 1:]
                     if statuses.get(step) not in done), active)
    return active


def reconcile_model_apply(project_id: str, proposal: dict) -> None:
    """An applied model is not a pending approval and not a finished workflow."""
    if proposal.get('proposal_type') != 'WIZARD_ENGINEERING_MODEL' or proposal.get('status') != 'APPLIED':
        return
    from . import conversation
    state = conversation.read()
    service = WorkflowStatusService(project_id)
    summary = service.get(summary=True)
    execution = summary.get('context', {}).get('agent_execution', {})
    if (state.get('active_proposal') != proposal['proposal_id']
            or extract_wizard_run_id(state.get('current_requirement', '')) != execution.get('run_id')
            or execution.get('state') != 'REVIEW_REQUIRED'):
        return
    check = summary['artifact_checks']['engineering_model']
    complete = check.get('complete', False)
    message = ('Engineering-Modell übernommen und vollständig geprüft. Der Auftrag kann mit Routing fortgesetzt werden.'
               if complete else 'Modell übernommen, aber die Workflow-Prüfung meldet noch Modelllücken: '
               + str({k: v for k, v in check.get('consistency', {}).items() if k != 'function_required' and v}))
    service.set_context({'agent_execution': {**execution, 'state': 'READY_TO_CONTINUE' if complete else 'BLOCKED',
        'message': message, 'updated_at': _now()}}, summary=True)


class WizardExecutionTracker:
    def __init__(self, project_id: str, run_id: str) -> None:
        self.project_id = project_id
        self.run_id = run_id
        self.step = "engineering_model"
        self.completed = 0
        self.total = 0

    def _workflow(self) -> WorkflowStatusService:
        return WorkflowStatusService(self.project_id)

    def update(
        self,
        state: str,
        message: str,
        *,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        token = activate_project(self.project_id)
        try:
            service = self._workflow()
            summary = service.get(summary=True)
            existing = summary.get('context', {}).get('agent_execution') or {}
            if existing.get('run_id') == self.run_id and existing.get('state') == 'CANCELED' and state != 'CANCELED':
                return
            self.step = execution_step(summary)
            if completed is not None:
                self.completed = max(0, int(completed))
            if total is not None:
                self.total = max(0, int(total))
            service.set_context({
                "agent_execution": {
                    "run_id": self.run_id,
                    "state": state,
                    "step": self.step,
                    "completed": self.completed,
                    "total": self.total,
                    "message": str(message or "Engineering-Auftrag wird verarbeitet.")[:1000],
                    "updated_at": _now(),
                },
            }, summary=True)
        finally:
            reset_project(token)

    def started(self) -> None:
        self.update("RUNNING", "Der bestätigte Engineering-Auftrag wurde serverseitig gestartet.")

    def heartbeat(self) -> None:
        self.update("RUNNING", "Der Engineering-Agent arbeitet im Hintergrund weiter.")

    def event(self, event: dict) -> None:
        if event.get("type") != "PROGRESS":
            return
        workload = event.get("workload") if isinstance(event.get("workload"), dict) else {}
        completed = workload.get("valid", workload.get("completed"))
        total = workload.get("requested", workload.get("total"))
        self.update(
            "RUNNING",
            str(event.get("text") or "Der Engineering-Agent arbeitet im Hintergrund weiter."),
            completed=int(completed) if isinstance(completed, (int, float)) else None,
            total=int(total) if isinstance(total, (int, float)) else None,
        )

    def finished(self, result: dict) -> None:
        status = str(result.get("status") or "INCOMPLETE").upper()
        message = str(result.get("text") or "Der Engineering-Auftrag wurde beendet.")
        if status in TERMINAL_SUCCESS:
            self.update("COMPLETED", message)
        elif status in TERMINAL_REVIEW:
            self.update("REVIEW_REQUIRED", message)
        else:
            self.update("BLOCKED", message)

    def failed(self, message: str) -> None:
        self.update("BLOCKED", message)
