"""Persistent wizard execution status for connection-independent agent runs."""

from __future__ import annotations

import json
from backend.agent_core.context.limits import MAX_REQUIREMENT_LENGTH
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from ..db import get_connection
from ..project_context import activate_project, reset_project
from ..workflow.service import WorkflowStatusService, WorkflowConflictError
from ..workflow.models import WORKFLOW_STEPS


WIZARD_RUN_PATTERN = re.compile(r"\bLauf-ID:\s*([A-Za-z0-9._-]{8,120})", re.IGNORECASE)
TERMINAL_SUCCESS = {"COMPLETED"}
TERMINAL_REVIEW = {"READY_FOR_REVIEW", "REVIEW_REQUIRED", "VALIDATED", "PROPOSED"}
# PIDs are reused across container restarts. Keep a process-incarnation token,
# not just the PID, as the durable owner of in-flight work.
SERVER_INSTANCE_ID = str(uuid4())


def extract_wizard_run_id(prompt: str) -> str | None:
    match = WIZARD_RUN_PATTERN.search(prompt or "")
    return match.group(1).rstrip(".") if match else None


def restore_wizard_continuation_prompt(prompt: str, wizard: dict | None, maximum: int = MAX_REQUIREMENT_LENGTH) -> str:
    """Reattach the durable confirmed request to compact continuation messages."""
    compact = str(prompt or "").strip()
    if not isinstance(wizard, dict) or "Strukturierte Vorgaben fuer den Engineering-Agenten:" in compact:
        return compact
    run_id = extract_wizard_run_id(compact)
    original = str(wizard.get("agent_prompt") or "").strip()
    if not run_id or wizard.get("run_id") != run_id or not original:
        return compact
    if "Strukturierte Vorgaben fuer den Engineering-Agenten:" not in original \
            or "per Wizard-Uebernehmen bestaetigt" not in original:
        return compact
    suffix = "\n\nFortsetzung des bestätigten Wizard-Auftrags:\n" + compact
    return original[:max(0, maximum - len(suffix))] + suffix


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def recover_interrupted_wizard_runs(project_id: str | None = None) -> int:
    """Mark RUNNING wizard rows owned by an old backend process as resumable."""
    current_pid = os.getpid()
    status_patch = json.dumps({
        "state": "BLOCKED",
        "recoverable": True,
        "message": (
            "Der Backend-Prozess wurde während des Engineering-Auftrags neu gestartet. "
            "Der bestätigte Lauf wird am letzten gespeicherten Schritt fortgesetzt."
        ),
        "updated_at": _now(),
        "server_pid": current_pid,
        "server_instance_id": SERVER_INSTANCE_ID,
    }, ensure_ascii=False)
    parameters: list[object] = [status_patch, str(current_pid), SERVER_INSTANCE_ID]
    project_filter = ""
    if project_id is not None:
        project_filter = " AND project_id = %s"
        parameters.append(project_id)
    with get_connection() as connection:
        rows = connection.execute(
            """
            UPDATE engineering_workflow_projects
            SET context = jsonb_set(
                    context,
                    '{agent_execution}',
                    (context -> 'agent_execution') || %s::jsonb,
                    true
                ),
                updated_at = now()
            WHERE context -> 'agent_execution' ->> 'state' = 'RUNNING'
              AND (COALESCE(context -> 'agent_execution' ->> 'server_pid', '') <> %s
                   OR COALESCE(context -> 'agent_execution' ->> 'server_instance_id', '') <> %s)
            """ + project_filter + " RETURNING project_id, context->'agent_execution'->>'run_id' AS wizard_run_id",
            tuple(parameters),
        ).fetchall()
        # Recovery transfers both halves of ownership in the same transaction.
        # A dead conversation lease must not reject the first resumed command.
        for row in rows:
            conversation = connection.execute(
                'SELECT state FROM engineering_agent_conversations WHERE project_id=%s FOR UPDATE',
                (row['project_id'],),
            ).fetchone()
            if conversation and extract_wizard_run_id(conversation['state'].get('current_requirement', '')) == row['wizard_run_id']:
                connection.execute("""UPDATE engineering_agent_conversations
                    SET state = state || %s::jsonb, modified_at=now() WHERE project_id=%s""",
                    (json.dumps({'run_id': None, 'lease_until': _now()}), row['project_id']))
    return len(rows)


def execution_step(summary: dict) -> str:
    """A continuation cannot reset an already completed artifact's progress."""
    context = summary.get('context') or {}
    request = context.get('wizard_request') or {}
    wizard = context.get('agent_wizard_status') or {}
    if request.get('version') == 2 and wizard.get('model_request_revision') != request.get('revision'):
        return 'engineering_model'
    active = summary.get('active_step') or 'engineering_model'
    statuses = summary.get('statuses') or {}
    done = {'COMPLETE', 'APPROVED', 'WARNING'}
    if active in WORKFLOW_STEPS and statuses.get(active) in done:
        return next((step for step in WORKFLOW_STEPS[WORKFLOW_STEPS.index(active) + 1:]
                     if statuses.get(step) not in done), active)
    return active


def reconcile_model_apply(project_id: str, proposal: dict) -> None:
    """Move an applied wizard proposal from the review gate to the next stale step."""
    proposal_type = str(proposal.get('proposal_type') or '')
    artifact_by_proposal = {
        'WIZARD_ENGINEERING_MODEL': 'engineering_model',
        'WIZARD_ROUTING': 'routing',
        'WIZARD_NETWORK_TOPOLOGY': 'network_editor',
        'CAPACITY_NETWORK_REPAIR': 'network_editor',
    }
    artifact = artifact_by_proposal.get(proposal_type)
    if artifact is None or proposal.get('status') != 'APPLIED':
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
    check = summary['artifact_checks'][artifact]
    complete = check.get('complete', False)
    if artifact == 'engineering_model' and complete:
        context = summary.get('context') or {}
        request = context.get('wizard_request') or {}
        wizard = context.get('agent_wizard_status') or {}
        if request.get('version') == 2 and request.get('run_id') == execution.get('run_id'):
            service.set_context({'agent_wizard_status': {**wizard, 'model_request_revision': request['revision']}}, summary=True)
            summary = service.get(summary=True)
    if complete:
        message = {
            'WIZARD_ENGINEERING_MODEL':
                'Engineering-Modell übernommen und vollständig geprüft. Der Auftrag kann mit Routing fortgesetzt werden.',
            'WIZARD_ROUTING':
                'Routing übernommen und vollständig geprüft. Der Auftrag kann mit der Netzwerktopologie fortgesetzt werden.',
            'WIZARD_NETWORK_TOPOLOGY':
                'Netzwerktopologie übernommen und vollständig geprüft. Capacity & Timing wird im nächsten Schritt neu berechnet.',
            'CAPACITY_NETWORK_REPAIR':
                'Capacity-Reparatur übernommen und vollständig geprüft. Capacity & Timing wird im nächsten Schritt neu berechnet.',
        }[proposal_type]
    else:
        details = check.get('consistency') or check.get('invalid') or check.get('counts') or {}
        message = f'{artifact} übernommen, aber die Workflow-Prüfung meldet noch Lücken: {details}'
        if artifact == 'routing' and check.get('coverage') and not check['coverage'].get('complete'):
            coverage = check['coverage']
            message = ('Routing übernommen. Im gespeicherten Simulationsumfang fehlen bestätigte Transporte für '
                       f"{len(coverage.get('missing_message_ids') or [])} Nachrichten und "
                       f"{len(coverage.get('missing_signal_ids') or [])} Signale. "
                       'Empfänger bzw. Transportanforderungen bestätigen oder den Umfang im Preflight begründet einschränken.')
    service.set_context({'agent_execution': {
        **execution,
        'state': 'READY_TO_CONTINUE' if complete else 'BLOCKED',
        'step': execution_step(summary),
        'message': message,
        'updated_at': _now(),
    }}, summary=True)


class WizardExecutionTracker:
    def __init__(self, project_id: str, run_id: str, *, owner_turn_id: str | None = None) -> None:
        self.project_id = project_id
        self.run_id = run_id
        self.step = "engineering_model"
        self.completed = 0
        self.total = 0
        self.owner_turn_id = owner_turn_id
        self._starting = False

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
            guard = None
            if not self._starting:
                if (existing.get('run_id') != self.run_id or existing.get('state') != 'RUNNING'
                        or (self.owner_turn_id is not None and existing.get('owner_turn_id') != self.owner_turn_id)):
                    return
                guard = {key: existing.get(key) for key in ('run_id', 'state', 'owner_turn_id')}
            self.step = execution_step(summary)
            request = summary.get('context', {}).get('wizard_request') or {}
            wizard = summary.get('context', {}).get('agent_wizard_status') or {}
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
                    "server_pid": os.getpid(),
                    "server_instance_id": SERVER_INSTANCE_ID,
                    "owner_turn_id": self.owner_turn_id,
                    "request_revision": request.get('revision'),
                    "model_review_required": request.get('version') == 2 and wizard.get('model_request_revision') != request.get('revision'),
                    "recoverable": False,
                },
            }, summary=True, execution_guard=guard)
        except WorkflowConflictError:
            # A newer finish/cancel/owner won the compare-and-set. A delayed
            # heartbeat is inert and must not resurrect or cancel that run.
            return
        finally:
            reset_project(token)

    def started(self) -> None:
        self._starting = True
        try:
            self.update("RUNNING", "Der bestätigte Engineering-Auftrag wurde serverseitig gestartet.")
        finally:
            self._starting = False

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
        elif status == "READY_TO_CONTINUE":
            self.update("READY_TO_CONTINUE", message)
        elif status in TERMINAL_REVIEW:
            self.update("REVIEW_REQUIRED", message)
        else:
            self.update("BLOCKED", message)

    def failed(self, message: str) -> None:
        self.update("BLOCKED", message)
