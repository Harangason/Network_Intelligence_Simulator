"""Server-owned authority, transactional project scope and structured failures."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable
from uuid import uuid4
from pydantic import ValidationError
from backend.agent_core.api.tool_contract import Permission, ToolResult, ToolStatus
from ..db import RequestUnit, ConcurrentUpdateError
from ..models import EngineeringValidationError
from ..project_context import activate_project, reset_project, normalize_context_project_id
from ..workflow.service import WorkflowStatusService, WorkflowConflictError
from .model import json_safe
from .audit import record

DEFAULT_PERMISSIONS = frozenset({Permission.READ_MODEL, Permission.GENERATE_PROPOSAL,
    Permission.VALIDATE, Permission.RUN_SIMULATION, Permission.ANALYZE_TRACE, Permission.EXECUTE_AUTHORIZED_GOAL})


@dataclass(frozen=True)
class PostCommitAction:
    dispatch: Callable[[], object]
    failed: Callable[[], None]


@dataclass(frozen=True)
class ToolAuthority:
    project_id: str
    actor: str = "engineering-agent"
    permissions: frozenset[Permission] = DEFAULT_PERMISSIONS
    progress_callback: Callable[[dict], None] | None = None

    def __post_init__(self):
        if not self.project_id.strip():
            raise ValueError("Ein aktives Projekt ist erforderlich.")
        object.__setattr__(self, "project_id", normalize_context_project_id(self.project_id))


def execute(authority: ToolAuthority, name: str, permission: Permission, arguments: dict,
            handler: Callable[[dict], object]) -> ToolResult:
    trace_id = str(uuid4())
    token = activate_project(authority.project_id)
    unit = RequestUnit(authority.project_id)
    from ..goal_execution.progress import sink
    progress_token = sink.set(authority.progress_callback)
    try:
        if permission not in authority.permissions:
            raise PermissionError(f"Berechtigung fehlt: {permission.value}")
        # Arguments never supply authority, actors, SQL, or a different project.
        forbidden = {"project_id", "active_project_id", "permissions", "actor", "approved_by"} & arguments.keys()
        if forbidden:
            raise PermissionError("Projekt und Berechtigungen werden vom Server festgelegt.")
        value = handler({**arguments, "_trace_id": trace_id, "_actor": authority.actor,
                         "_permissions": [p.value for p in authority.permissions]})
        if isinstance(value, PostCommitAction):
            record(trace_id,authority.actor,"DISPATCH_PENDING",name,"SUCCESS",{"argument_keys":sorted(arguments)})
            unit.finish(True)
            try:
                value = value.dispatch()
            except Exception:
                value.failed()
                unit.finish(True)
                raise
        result = value if isinstance(value, ToolResult) else ToolResult(data=json_safe(value))
        result.trace_id = trace_id
        if unit.model_changed:
            WorkflowStatusService(authority.project_id).mark_changed("engineering_model", "Freigegebener Engineering-Vorschlag übernommen", actor=authority.actor)
        record(trace_id, authority.actor, "TOOL_CALL", name, result.status.value,
               {"argument_keys": sorted(arguments), "affected_objects": result.affected_objects,
                "success": result.success, "findings": result.findings,
                "result": {key: result.data[key] for key in ("proposal_id", "revision", "status", "workload_id", "validation_result", "canonical_ids", "requested", "valid") if key in result.data} if isinstance(result.data, dict) else {}})
        unit.finish(True)
        return result
    except Exception as error:
        unit.finish(False)
        if isinstance(error, PermissionError):
            status = ToolStatus.PERMISSION_DENIED
        elif isinstance(error, (ConcurrentUpdateError, WorkflowConflictError)):
            status = ToolStatus.CONFLICT
        elif isinstance(error, LookupError) and not isinstance(error, KeyError):
            status = ToolStatus.NOT_FOUND
        elif isinstance(error, (ValueError, KeyError, TypeError, EngineeringValidationError, ValidationError)):
            status = ToolStatus.INVALID_INPUT
        else:
            status = ToolStatus.INTERNAL_ERROR
            logging.getLogger(__name__).exception("Engineering tool %s failed (%s)", name, trace_id)
        message = str(error) if status != ToolStatus.INTERNAL_ERROR else "Der Fachdienst ist fehlgeschlagen. Details stehen im Serverprotokoll."
        result = ToolResult(success=False, status=status, trace_id=trace_id,
                            findings=[{"severity": "ERROR", "message": message}], next_actions=["Eingaben oder Dienststatus prüfen"])
        try:
            record(trace_id, authority.actor, "TOOL_CALL", name, status.value, {"argument_keys": sorted(arguments), "error": message})
            unit.finish(True)
        except Exception:
            unit.finish(False)
            logging.getLogger(__name__).exception("Tool audit failed (%s)", trace_id)
        return result
    finally:
        sink.reset(progress_token)
        unit.close()
        reset_project(token)
