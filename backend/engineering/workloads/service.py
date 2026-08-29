"""Persistenter Orchestrator fuer messbare Engineering-Agent-Auftraege."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

try:
    from backend.agent_core.context import ContextBuilder
    from backend.agent_core.errors import AgentCoreValidationError
    from backend.agent_core.orchestration import RetryManager, WorkloadExecutionLoop, WorkloadPlanner, WorkloadProgressTracker
    from backend.agent_core.proposals import ApprovalBoundary, InMemoryProposalStore
    from backend.agent_core.registry import GeneratorRegistry, ValidatorRegistry
    from backend.agent_core.validation import CompletionValidator
except ModuleNotFoundError:  # Tests execute with backend as the import root.
    from agent_core.context import ContextBuilder
    from agent_core.errors import AgentCoreValidationError
    from agent_core.orchestration import RetryManager, WorkloadExecutionLoop, WorkloadPlanner, WorkloadProgressTracker
    from agent_core.proposals import ApprovalBoundary, InMemoryProposalStore
    from agent_core.registry import GeneratorRegistry, ValidatorRegistry
    from agent_core.validation import CompletionValidator
from psycopg.types.json import Jsonb

from ..db import get_connection
from ..models import EngineeringValidationError, validate_uuid
from ..project_context import current_project_id
from ..proposals import (
    approve_proposal,
    create_proposal,
    get_proposal,
    update_proposal,
    validate_proposal,
)
from ..repository import list_objects
from .generators import default_signal_generators
from .handlers import SignalGenerationWorkloadHandler, StructuredObjectWorkloadHandler, normalized_name
from .models import WORKLOAD_STATUSES, WORKLOAD_TYPES, parse_workload_request
from .registry import WorkloadTypeRegistry

PROPOSAL_RESOURCES = {
    "HardwareNode": "hardware-nodes",
    "Function": "functions",
    "Interface": "interfaces",
    "Message": "messages",
    "Signal": "signals",
}


def _registry() -> WorkloadTypeRegistry:
    registry = WorkloadTypeRegistry()
    registry.register(SignalGenerationWorkloadHandler())
    for workload_type in WORKLOAD_TYPES:
        if workload_type != "SIGNAL_GENERATION":
            registry.register(StructuredObjectWorkloadHandler(workload_type))
    return registry


def _generator_registry() -> GeneratorRegistry:
    registry = GeneratorRegistry()
    for generator in default_signal_generators():
        registry.register(generator)
    return registry


def _validator_registry() -> ValidatorRegistry:
    registry = ValidatorRegistry()
    for workload_type in WORKLOAD_TYPES:
        registry.register(CompletionValidator(), workload_type, "completion")
    return registry


class EngineeringWorkloadOrchestrator:
    """Coordinates plan, generation, validation, repair, counting and review."""

    def __init__(
        self,
        project_id: str | None = None,
        registry: WorkloadTypeRegistry | None = None,
        generator_registry: GeneratorRegistry | None = None,
        validator_registry: ValidatorRegistry | None = None,
    ) -> None:
        self.project_id = (project_id or current_project_id()).strip() or "default"
        self.registry = registry or _registry()
        self.handler_registry = self.registry
        self.generator_registry = generator_registry or _generator_registry()
        self.validator_registry = validator_registry or _validator_registry()
        self.planner = WorkloadPlanner(parse_workload_request)
        self.completion_validator = CompletionValidator()
        self.progress_tracker = WorkloadProgressTracker()
        self.retry_manager = RetryManager()
        self.execution_loop = WorkloadExecutionLoop(self.retry_manager)
        self.context_builder = ContextBuilder(engineering_provider=self._engineering_context_provider)
        self.approval_boundary = ApprovalBoundary(InMemoryProposalStore())

    # ------------------------------------------------------------------
    # Persistence and audit
    # ------------------------------------------------------------------

    def create_workload(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self.planner.plan(payload)
        with get_connection() as connection:
            workload = connection.execute(
                "INSERT INTO engineering_workloads "
                "(project_id, parent_workload_id, workload_type, title, description, prompt, domain, "
                "target_object, requested_total, requested_count, constraints, dependencies, validation_rules, "
                "completion_criteria, max_generation_attempts, agent, model, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING *",
                (
                    self.project_id,
                    plan.get("parent_workload_id"),
                    plan["workload_type"],
                    plan["title"],
                    plan["description"],
                    plan["prompt"],
                    plan.get("domain"),
                    plan["target_object"],
                    plan["requested_total"],
                    plan["requested_total"],
                    Jsonb(plan["constraints"]),
                    Jsonb(plan["dependencies"]),
                    Jsonb(plan["validation_rules"]),
                    Jsonb(plan["completion_criteria"]),
                    plan["max_generation_attempts"],
                    plan.get("agent"),
                    plan.get("model"),
                    plan.get("created_by"),
                ),
            ).fetchone()
            for package in plan["work_packages"]:
                connection.execute(
                    "INSERT INTO engineering_work_packages "
                    "(workload_id, package_code, category, target_object, requested_count, missing_count, "
                    "max_generation_attempts, configuration) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        workload["workload_id"],
                        package["package_code"],
                        package["category"],
                        package["target_object"],
                        package["requested_count"],
                        package["requested_count"],
                        package["max_generation_attempts"],
                        Jsonb(package.get("configuration") or {}),
                    ),
                )
                self._audit_with_connection(
                    connection,
                    workload,
                    "WORK_PACKAGE_CREATED",
                    {
                        "package_code": package["package_code"],
                        "category": package["category"],
                        "requested_count": package["requested_count"],
                    },
                    actor=plan.get("created_by"),
                )
            for dependency in plan["dependencies"]:
                if not isinstance(dependency, dict) or not dependency.get("workload_id"):
                    continue
                self._validate_dependency(connection, str(dependency["workload_id"]))
                connection.execute(
                    "INSERT INTO engineering_workload_dependencies "
                    "(workload_id, dependency_workload_id, required_status) VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        workload["workload_id"],
                        dependency["workload_id"],
                        str(dependency.get("required_status") or "COMPLETED").upper(),
                    ),
                )
            self._audit_with_connection(
                connection,
                workload,
                "WORKLOAD_RECEIVED",
                {"requested_total": plan["requested_total"]},
                actor=plan.get("created_by"),
            )
            self._audit_with_connection(
                connection,
                workload,
                "WORKLOAD_CREATED",
                {"requested_total": plan["requested_total"], "packages": plan["work_packages"]},
                actor=plan.get("created_by"),
            )
            connection.commit()
        return self.get_workload(str(workload["workload_id"]))

    def _validate_dependency(self, connection, workload_id: str) -> None:
        validate_uuid(workload_id)
        row = connection.execute(
            "SELECT 1 FROM engineering_workloads WHERE workload_id = %s AND project_id = %s",
            (workload_id, self.project_id),
        ).fetchone()
        if row is None:
            raise EngineeringValidationError(f"Dependency-Workload {workload_id} wurde nicht gefunden.")

    def list_workloads(
        self,
        *,
        status: str | None = None,
        workload_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["project_id = %s"]
        values: list[Any] = [self.project_id]
        if status:
            status = status.upper()
            if status not in WORKLOAD_STATUSES:
                raise EngineeringValidationError(f"Unbekannter Workload-Status: {status!r}.")
            clauses.append("status = %s")
            values.append(status)
        if workload_type:
            workload_type = workload_type.upper()
            if workload_type not in WORKLOAD_TYPES:
                raise EngineeringValidationError(f"Unbekannter Workload-Typ: {workload_type!r}.")
            clauses.append("workload_type = %s")
            values.append(workload_type)
        values.extend((min(max(limit, 1), 500), max(offset, 0)))
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM engineering_workloads WHERE "
                + " AND ".join(clauses)
                + " ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                values,
            ).fetchall()
        return rows

    def get_workload(self, workload_id: str) -> dict[str, Any]:
        validate_uuid(workload_id)
        with get_connection() as connection:
            workload = connection.execute(
                "SELECT * FROM engineering_workloads WHERE workload_id = %s AND project_id = %s",
                (workload_id, self.project_id),
            ).fetchone()
            if workload is None:
                raise EngineeringValidationError(f"Workload {workload_id} wurde nicht gefunden.")
            packages = connection.execute(
                "SELECT * FROM engineering_work_packages WHERE workload_id = %s ORDER BY package_code",
                (workload_id,),
            ).fetchall()
        return {**workload, "work_packages": packages, "dependencies_resolved": self.dependencies(workload_id)}

    def list_workload_objects(self, workload_id: str, work_package_id: str | None = None) -> list[dict[str, Any]]:
        validate_uuid(workload_id)
        values: list[Any] = [workload_id]
        package_clause = ""
        if work_package_id:
            validate_uuid(work_package_id)
            package_clause = " AND work_package_id = %s"
            values.append(work_package_id)
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM engineering_workload_objects WHERE workload_id = %s"
                + package_clause
                + " ORDER BY category, created_at, object_key",
                values,
            ).fetchall()
        return rows

    def list_events(self, workload_id: str, limit: int = 200) -> list[dict[str, Any]]:
        validate_uuid(workload_id)
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM engineering_workload_events "
                "WHERE workload_id = %s AND project_id = %s ORDER BY occurred_at DESC LIMIT %s",
                (workload_id, self.project_id, min(max(limit, 1), 1000)),
            ).fetchall()

    def _audit_with_connection(
        self,
        connection,
        workload: dict[str, Any],
        event_type: str,
        details: dict[str, Any] | None = None,
        *,
        package_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO engineering_workload_events "
            "(project_id, workload_id, work_package_id, event_type, actor, agent, model, details) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                self.project_id,
                workload["workload_id"],
                package_id,
                event_type,
                actor,
                workload.get("agent"),
                workload.get("model"),
                Jsonb(details or {}),
            ),
        )

    def audit(
        self,
        workload: dict[str, Any],
        event_type: str,
        details: dict[str, Any] | None = None,
        *,
        package_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        with get_connection() as connection:
            self._audit_with_connection(connection, workload, event_type, details, package_id=package_id, actor=actor)
            connection.commit()

    # ------------------------------------------------------------------
    # Orchestration and completion loop
    # ------------------------------------------------------------------

    def start_workload(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if workload["status"] in {"CANCELED", "FAILED", "COMPLETED"}:
            return workload
        self._set_workload_status(workload_id, "PLANNING", actor=actor, start=True)
        workload = self.get_workload(workload_id)
        handler = self.registry.get(str(workload["workload_type"]))
        self.audit(workload, "PLANNING_STARTED", {"handler": type(handler).__name__}, actor=actor)
        self.audit(workload, "HANDLER_SELECTED", {"handler": type(handler).__name__}, actor=actor)
        handler.plan(self, workload, workload["work_packages"])

        def execute_cycle(current: dict[str, Any]) -> None:
            self._begin_attempt(workload_id, actor=actor)
            current = self.get_workload(workload_id)
            for package in current["work_packages"]:
                if package["status"] in {"COMPLETED", "READY_FOR_REVIEW", "CANCELED", "BLOCKED"}:
                    continue
                self._begin_package_attempt(package)
                self.audit(current, "WORK_PACKAGE_STARTED", {"package_code": package["package_code"]}, package_id=str(package["work_package_id"]), actor=actor)
                result = handler.execute(self, current, package)
                self.audit(current, "GENERATOR_EXECUTED", result, package_id=str(package["work_package_id"]), actor=actor)

            self._set_workload_status(workload_id, "VALIDATING", actor=actor)
            current = self.get_workload(workload_id)
            validation = handler.validate(self, current)
            self.audit(current, "VALIDATION_EXECUTED", validation, actor=actor)
            current = self.get_workload(workload_id)
            if any(int(package["invalid_count"]) > 0 for package in current["work_packages"]):
                repair = handler.repair(self, current)
                self.audit(current, "REPAIR_EXECUTED", repair, actor=actor)
                if int(repair.get("repaired") or 0) > 0:
                    handler.validate(self, self.get_workload(workload_id))

        return self.execution_loop.run(
            inspect=lambda: self.get_workload(workload_id),
            execute_cycle=execute_cycle,
            evaluate=lambda: self.evaluate_workload_completion(workload_id, actor=actor),
            progress_token=lambda current: (int(current["generated_count"]), int(current["valid_count"])),
        )

    def _begin_attempt(self, workload_id: str, *, actor: str | None = None) -> None:
        with get_connection() as connection:
            workload = connection.execute(
                "UPDATE engineering_workloads SET status = 'IN_PROGRESS', attempts = attempts + 1, "
                "started_at = COALESCE(started_at, now()), updated_at = now() "
                "WHERE workload_id = %s AND project_id = %s RETURNING *",
                (workload_id, self.project_id),
            ).fetchone()
            self._audit_with_connection(connection, workload, "WORKLOAD_ATTEMPT_STARTED", {"attempt": workload["attempts"]}, actor=actor)
            if int(workload["attempts"]) > 1:
                self._audit_with_connection(
                    connection,
                    workload,
                    "RETRY_EXECUTED",
                    {"attempt": workload["attempts"], "reason": "WORKLOAD_INCOMPLETE"},
                    actor=actor,
                )
            connection.commit()

    def _begin_package_attempt(self, package: dict[str, Any]) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_work_packages SET status = 'IN_PROGRESS', attempts = attempts + 1, "
                "started_at = COALESCE(started_at, now()), updated_at = now() WHERE work_package_id = %s",
                (package["work_package_id"],),
            )
            connection.commit()

    def _set_workload_status(
        self,
        workload_id: str,
        status: str,
        *,
        actor: str | None = None,
        start: bool = False,
    ) -> dict[str, Any]:
        status = status.upper()
        if status not in WORKLOAD_STATUSES:
            raise EngineeringValidationError(f"Unbekannter Workload-Status: {status!r}.")
        started = ", started_at = COALESCE(started_at, now())" if start else ""
        with get_connection() as connection:
            workload = connection.execute(
                f"UPDATE engineering_workloads SET status = %s, updated_at = now(){started} "
                "WHERE workload_id = %s AND project_id = %s RETURNING *",
                (status, workload_id, self.project_id),
            ).fetchone()
            if workload is None:
                raise EngineeringValidationError(f"Workload {workload_id} wurde nicht gefunden.")
            self._audit_with_connection(connection, workload, "WORKLOAD_STATUS_CHANGED", {"status": status}, actor=actor)
            connection.commit()
        return workload

    def evaluate_workload_completion(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        self.sync_workload_approvals(workload_id)
        self.recount_packages(workload_id)
        workload = self.get_workload(workload_id)
        objects = self.list_workload_objects(workload_id)
        try:
            decision = self.completion_validator.evaluate(
                workload,
                workload["work_packages"],
                objects,
                workload["dependencies_resolved"],
            )
        except AgentCoreValidationError as error:
            raise EngineeringValidationError(str(error)) from error
        findings = [
            finding
            for package in workload["work_packages"]
            for finding in package.get("findings") or []
            if isinstance(finding, dict)
        ]
        created_objects = [str(item["workload_object_id"]) for item in objects]
        completed_sql = ", completed_at = COALESCE(completed_at, now())" if decision["status"] == "COMPLETED" else ""
        with get_connection() as connection:
            updated = connection.execute(
                "UPDATE engineering_workloads SET status = %s, requested_count = %s, generated_count = %s, "
                "valid_count = %s, invalid_count = %s, duplicate_count = %s, missing_count = %s, "
                "metrics = %s, findings = %s, created_objects = %s, updated_at = now()"
                + completed_sql
                + " WHERE workload_id = %s AND project_id = %s RETURNING *",
                (
                    decision["status"],
                    decision["requested_count"],
                    decision["generated_count"],
                    decision["valid_count"],
                    decision["invalid_count"],
                    decision["duplicate_count"],
                    decision["missing_count"],
                    Jsonb(decision["metrics"]),
                    Jsonb(findings),
                    Jsonb(created_objects),
                    workload_id,
                    self.project_id,
                ),
            ).fetchone()
            event = "READY_FOR_REVIEW" if decision["status"] == "READY_FOR_REVIEW" else "COMPLETION_EVALUATED"
            self._audit_with_connection(connection, updated, event, decision, actor=actor)
            self._audit_with_connection(connection, updated, "PROGRESS_UPDATED", decision["metrics"], actor=actor)
            connection.commit()
        return {**self.get_workload(workload_id), "completion": decision}

    def validate_workload(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        handler = self.registry.get(str(workload["workload_type"]))
        self._set_workload_status(workload_id, "VALIDATING", actor=actor)
        validation = handler.validate(self, self.get_workload(workload_id))
        self.audit(workload, "VALIDATION_EXECUTED", validation, actor=actor)
        return self.evaluate_workload_completion(workload_id, actor=actor)

    def generate_missing(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if int(workload["attempts"]) >= int(workload["max_generation_attempts"]):
            return self.evaluate_workload_completion(workload_id, actor=actor)
        self.audit(workload, "GENERATE_MISSING_REQUESTED", {}, actor=actor)
        return self.start_workload(workload_id, actor=actor)

    def retry_invalid(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if int(workload["attempts"]) >= int(workload["max_generation_attempts"]):
            return self.evaluate_workload_completion(workload_id, actor=actor)
        handler = self.registry.get(str(workload["workload_type"]))
        repair = handler.repair(self, workload)
        self.audit(workload, "REPAIR_ATTEMPTED", repair, actor=actor)
        handler.validate(self, self.get_workload(workload_id))
        return self.evaluate_workload_completion(workload_id, actor=actor)

    # ------------------------------------------------------------------
    # User controls
    # ------------------------------------------------------------------

    def pause(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if workload["status"] in {"COMPLETED", "CANCELED", "FAILED"}:
            raise EngineeringValidationError("Dieser Workload kann nicht pausiert werden.")
        return self._set_workload_status(workload_id, "PAUSED", actor=actor)

    def resume(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if workload["status"] == "CANCELED":
            raise EngineeringValidationError("Ein abgebrochener Workload kann nicht fortgesetzt werden.")
        self._set_workload_status(workload_id, "IN_PROGRESS", actor=actor)
        self.audit(workload, "WORKLOAD_RESUMED", {}, actor=actor)
        return self.start_workload(workload_id, actor=actor)

    def cancel(self, workload_id: str, *, actor: str | None = None) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        if workload["status"] == "COMPLETED":
            raise EngineeringValidationError("Ein abgeschlossener Workload kann nicht abgebrochen werden.")
        return self._set_workload_status(workload_id, "CANCELED", actor=actor)

    def approve_valid(
        self,
        workload_id: str,
        *,
        actor: str,
        selections: dict[str, list[int]] | None = None,
    ) -> dict[str, Any]:
        try:
            self.approval_boundary.require_human(actor)
        except AgentCoreValidationError as error:
            raise EngineeringValidationError(str(error)) from error
        workload = self.get_workload(workload_id)
        objects = self.list_workload_objects(workload_id)
        proposal_ids = sorted({str(item["proposal_id"]) for item in objects if item.get("proposal_id")})
        approved: list[str] = []
        for proposal_id in proposal_ids:
            proposal = get_proposal(proposal_id)
            if proposal["status"] in {"APPROVED", "REJECTED", "SUPERSEDED"}:
                continue
            validation = proposal.get("validation_results") or []
            indexes = selections.get(proposal_id) if selections else [
                int(item["index"])
                for item in validation
                if item.get("valid") and not (proposal.get("proposed_objects") or [])[int(item["index"])].get("canonical_id")
            ]
            if indexes:
                approve_proposal(proposal_id, indexes=indexes, actor=actor)
                approved.append(proposal_id)
        self.audit(workload, "OBJECTS_APPROVED", {"proposal_ids": approved}, actor=actor)
        return self.evaluate_workload_completion(workload_id, actor=actor)

    # ------------------------------------------------------------------
    # Handler support
    # ------------------------------------------------------------------

    def list_canonical_objects(self, object_type: str) -> list[dict[str, Any]]:
        return list_objects(object_type, limit=500)

    def _engineering_context_provider(
        self,
        workload: dict[str, Any],
        package: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if str(workload.get("workload_type") or "") == "SIGNAL_GENERATION" and package:
            return self.resolve_signal_context(str(package.get("category") or "general").lower())
        return {"project_id": self.project_id}

    def build_context(
        self,
        workload: dict[str, Any],
        package: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.context_builder.build(workload, package).as_dict()

    def resolve_signal_context(self, category: str) -> dict[str, Any]:
        hardware = self.list_canonical_objects("HardwareNode")
        interfaces = self.list_canonical_objects("Interface")
        messages = self.list_canonical_objects("Message")

        def score(node: dict[str, Any]) -> int:
            name = normalized_name(node.get("name"))
            if category == "thermal":
                if name == "thermalecu":
                    return 100
                if "thermal" in name and "ecu" in name:
                    return 90
                if "temperatur" in name:
                    return 70
            if category == "motion":
                if name == "motionecu":
                    return 100
                if "motion" in name and "ecu" in name:
                    return 90
                if "motion" in name:
                    return 70
            return 0

        candidates = sorted(hardware, key=score, reverse=True)
        node = candidates[0] if candidates and score(candidates[0]) > 0 else None
        engineering_interface = next(
            (item for item in interfaces if node and str(item.get("hardware_node_id")) == str(node.get("id"))),
            None,
        )
        expected_name = "ThermalECU_SignalBatch" if category == "thermal" else "MotionECU_SignalBatch"
        message = next((item for item in messages if normalized_name(item.get("name")) == normalized_name(expected_name)), None)
        if message is None and engineering_interface:
            message = next(
                (
                    item
                    for item in messages
                    if str(item.get("interface_id")) == str(engineering_interface.get("id"))
                    and int(item.get("dlc") or 0) >= 64
                ),
                None,
            )
        return {
            "node": node,
            "engineering_interface": engineering_interface,
            "message": message,
            "expected_message_name": expected_name,
            "consumers": [],
        }

    def ensure_message_dependency(
        self,
        workload: dict[str, Any],
        package: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        configuration = dict(package.get("configuration") or {})
        dependency_id = configuration.get("message_dependency_workload_id")
        if dependency_id:
            try:
                self.get_workload(str(dependency_id))
                return
            except EngineeringValidationError:
                pass
        category = str(package["category"])
        engineering_interface = context["engineering_interface"]
        message_name = context["expected_message_name"]
        message_id_hex = "0x5A0" if category == "thermal" else "0x5A1"
        candidate = {
            "object_type": "Message",
            "resource": "messages",
            "name": message_name,
            "description": f"CAN-FD-Container fuer den {category}-Signal-Workload.",
            "domain": workload.get("domain") or "automotive",
            "interface_id": str(engineering_interface["id"]),
            "message_id_hex": message_id_hex,
            "direction": "tx",
            "cycle_ms": 10,
            "dlc": 64,
        }
        child = self.create_workload(
            {
                "prompt": f"Erzeuge 1 Message fuer den {category}-Signal-Workload.",
                "workload_type": "MESSAGE_GENERATION",
                "target_object": "Message",
                "requested_total": 1,
                "parent_workload_id": str(workload["workload_id"]),
                "domain": workload.get("domain"),
                "created_by": workload.get("created_by"),
                "agent": workload.get("agent"),
                "model": workload.get("model"),
                "work_packages": [
                    {
                        "category": f"{category}-message",
                        "requested_count": 1,
                        "configuration": {"candidate_objects": [candidate]},
                    }
                ],
            }
        )
        child = self.start_workload(str(child["workload_id"]), actor="engineering-workload-orchestrator")
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO engineering_workload_dependencies "
                "(workload_id, dependency_workload_id, required_status) VALUES (%s, %s, 'COMPLETED') "
                "ON CONFLICT DO NOTHING",
                (workload["workload_id"], child["workload_id"]),
            )
            configuration["message_dependency_workload_id"] = str(child["workload_id"])
            connection.execute(
                "UPDATE engineering_work_packages SET configuration = %s, updated_at = now() WHERE work_package_id = %s",
                (Jsonb(configuration), package["work_package_id"]),
            )
            self._audit_with_connection(
                connection,
                workload,
                "DEPENDENCY_WORKLOAD_CREATED",
                {"dependency_workload_id": str(child["workload_id"]), "category": category},
                package_id=str(package["work_package_id"]),
            )
            connection.commit()

    def dependencies(self, workload_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT d.dependency_workload_id, d.required_status, w.status, w.title, w.workload_type, "
                "w.valid_count, w.requested_total FROM engineering_workload_dependencies d "
                "JOIN engineering_workloads w ON w.workload_id = d.dependency_workload_id "
                "WHERE d.workload_id = %s AND w.project_id = %s ORDER BY w.created_at",
                (workload_id, self.project_id),
            ).fetchall()
        return [
            {
                **row,
                "satisfied": row["status"] == row["required_status"]
                or (row["required_status"] == "READY_FOR_REVIEW" and row["status"] == "COMPLETED"),
            }
            for row in rows
        ]

    def block_package(self, package: dict[str, Any], code: str, message: str) -> None:
        findings = [
            *[item for item in package.get("findings") or [] if item.get("code") != code],
            {"code": code, "severity": "ERROR", "message": message},
        ]
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_work_packages SET status = 'BLOCKED', findings = %s, updated_at = now() "
                "WHERE work_package_id = %s",
                (Jsonb(findings), package["work_package_id"]),
            )
            connection.commit()

    def unblock_package(self, package: dict[str, Any]) -> None:
        if package.get("status") != "BLOCKED":
            return
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_work_packages SET status = 'RECEIVED', findings = '[]'::jsonb, updated_at = now() "
                "WHERE work_package_id = %s",
                (package["work_package_id"],),
            )
            connection.commit()

    def create_validated_proposal(
        self,
        workload: dict[str, Any],
        package: dict[str, Any],
        object_type: str,
        definitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        resource = PROPOSAL_RESOURCES.get(object_type)
        if not resource:
            raise EngineeringValidationError(f"{object_type} besitzt keinen Engineering-Proposal-Adapter.")
        proposed = [
            {**definition, "object_type": object_type, "resource": resource}
            for definition in definitions
        ]
        proposal = create_proposal(
            {
                "proposal_type": "OBJECT",
                "target_object": {"resource": resource, "workload_id": str(workload["workload_id"])},
                "prompt": workload["prompt"],
                "model": workload.get("model") or "engineering-workload-orchestrator-v1",
                "proposed_objects": proposed,
                "evidence": [
                    {
                        "type": "ENGINEERING_WORKLOAD",
                        "workload_id": str(workload["workload_id"]),
                        "work_package_id": str(package["work_package_id"]),
                        "requested_count": package["requested_count"],
                    }
                ],
                "retrieved_context": [],
                "validation_results": [],
                "created_by": workload.get("created_by") or "engineering-workload-orchestrator",
                "confidence": 0.95,
            }
        )
        proposal = validate_proposal(str(proposal["proposal_id"]), actor="engineering-workload-orchestrator")
        self.audit(
            workload,
            "PROPOSAL_READY_FOR_REVIEW" if proposal["status"] == "READY_FOR_REVIEW" else "PROPOSAL_VALIDATION_FAILED",
            {"proposal_id": str(proposal["proposal_id"]), "status": proposal["status"], "count": len(definitions)},
            package_id=str(package["work_package_id"]),
        )
        return proposal

    def upsert_workload_object(
        self,
        workload: dict[str, Any],
        package: dict[str, Any],
        object_key: str,
        definition: dict[str, Any],
        *,
        canonical_id: str | None = None,
        proposal_id: str | None = None,
        proposal_index: int | None = None,
        review_state: str = "UNREVIEWED",
        approval_state: str = "PENDING",
    ) -> dict[str, Any]:
        with get_connection() as connection:
            row = connection.execute(
                "INSERT INTO engineering_workload_objects "
                "(workload_id, work_package_id, object_type, object_key, category, definition, canonical_id, "
                "proposal_id, proposal_index, review_state, approval_state) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (workload_id, object_key) DO UPDATE SET definition = EXCLUDED.definition, "
                "canonical_id = COALESCE(EXCLUDED.canonical_id, engineering_workload_objects.canonical_id), "
                "proposal_id = COALESCE(EXCLUDED.proposal_id, engineering_workload_objects.proposal_id), "
                "proposal_index = COALESCE(EXCLUDED.proposal_index, engineering_workload_objects.proposal_index), "
                "review_state = EXCLUDED.review_state, approval_state = EXCLUDED.approval_state, updated_at = now() "
                "RETURNING *",
                (
                    workload["workload_id"],
                    package["work_package_id"],
                    workload["target_object"],
                    object_key,
                    package["category"],
                    Jsonb(definition),
                    canonical_id,
                    proposal_id,
                    proposal_index,
                    review_state,
                    approval_state,
                ),
            ).fetchone()
            self._audit_with_connection(
                connection,
                workload,
                "OBJECTS_GENERATED",
                {"workload_object_id": str(row["workload_object_id"]), "object_key": object_key},
                package_id=str(package["work_package_id"]),
            )
            connection.commit()
        return row

    def update_workload_object_validation(
        self,
        item: dict[str, Any],
        definition: dict[str, Any],
        findings: list[dict[str, Any]],
        *,
        duplicate_of: str | None = None,
    ) -> None:
        errors = [finding for finding in findings if str(finding.get("severity") or "ERROR").upper() == "ERROR"]
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_workload_objects SET definition = %s, validation_results = %s, "
                "is_valid = %s, is_duplicate = %s, duplicate_of = %s, updated_at = now() "
                "WHERE workload_object_id = %s",
                (
                    Jsonb(definition),
                    Jsonb(findings),
                    not errors,
                    bool(duplicate_of),
                    duplicate_of,
                    item["workload_object_id"],
                ),
            )
            connection.commit()

    def replace_workload_object_definition(self, item: dict[str, Any], definition: dict[str, Any]) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_workload_objects SET definition = %s, validation_results = '[]'::jsonb, "
                "is_valid = FALSE, updated_at = now() WHERE workload_object_id = %s",
                (Jsonb(definition), item["workload_object_id"]),
            )
            connection.commit()

    def sync_workload_proposals(self, workload_id: str) -> None:
        objects = self.list_workload_objects(workload_id)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in objects:
            if item.get("proposal_id"):
                grouped[str(item["proposal_id"])].append(item)
        for proposal_id, items in grouped.items():
            proposal = get_proposal(proposal_id)
            if proposal["status"] in {"APPROVED", "SUPERSEDED", "REJECTED"}:
                continue
            proposed = [dict(item) for item in proposal.get("proposed_objects") or []]
            for item in items:
                index = item.get("proposal_index")
                if isinstance(index, int) and 0 <= index < len(proposed):
                    proposed[index] = {**dict(item["definition"]), "object_type": item["object_type"], "resource": PROPOSAL_RESOURCES.get(item["object_type"])}
            update_proposal(proposal_id, {"proposed_objects": proposed, "actor": "engineering-workload-orchestrator"})
            validate_proposal(proposal_id, actor="engineering-workload-orchestrator")

    def sync_workload_approvals(self, workload_id: str) -> None:
        objects = self.list_workload_objects(workload_id)
        proposals: dict[str, dict[str, Any]] = {}
        for item in objects:
            if not item.get("proposal_id"):
                continue
            proposal_id = str(item["proposal_id"])
            if proposal_id not in proposals:
                proposals[proposal_id] = get_proposal(proposal_id)
            proposal = proposals[proposal_id]
            index = item.get("proposal_index")
            proposed = proposal.get("proposed_objects") or []
            proposed_item = proposed[index] if isinstance(index, int) and 0 <= index < len(proposed) else {}
            canonical_id = proposed_item.get("canonical_id")
            review_state = "REVIEWED" if canonical_id else ("READY_FOR_REVIEW" if proposal["status"] == "READY_FOR_REVIEW" else "DRAFT")
            approval_state = "APPROVED" if canonical_id else "PENDING"
            with get_connection() as connection:
                connection.execute(
                    "UPDATE engineering_workload_objects SET canonical_id = COALESCE(%s, canonical_id), "
                    "review_state = %s, approval_state = %s, updated_at = now() WHERE workload_object_id = %s",
                    (canonical_id, review_state, approval_state, item["workload_object_id"]),
                )
                connection.commit()

    def recount_packages(self, workload_id: str) -> None:
        workload = self.get_workload(workload_id)
        for package in workload["work_packages"]:
            objects = self.list_workload_objects(workload_id, str(package["work_package_id"]))
            generated = len(objects)
            valid = sum(bool(item.get("is_valid")) and not bool(item.get("is_duplicate")) for item in objects)
            duplicates = sum(bool(item.get("is_duplicate")) for item in objects)
            invalid = sum(not bool(item.get("is_valid")) and not bool(item.get("is_duplicate")) for item in objects)
            missing = max(0, int(package["requested_count"]) - valid)
            all_approved = bool(objects) and all(
                item.get("canonical_id") and item.get("approval_state") == "APPROVED"
                for item in objects
                if item.get("is_valid") and not item.get("is_duplicate")
            )
            if package["status"] == "BLOCKED" and missing:
                status = "BLOCKED"
            elif valid == int(package["requested_count"]) and invalid == 0 and duplicates == 0:
                status = "COMPLETED" if all_approved else "READY_FOR_REVIEW"
            elif int(package["attempts"]) >= int(package["max_generation_attempts"]):
                status = "INCOMPLETE"
            else:
                status = "IN_PROGRESS"
            with get_connection() as connection:
                connection.execute(
                    "UPDATE engineering_work_packages SET generated_count = %s, valid_count = %s, invalid_count = %s, "
                    "duplicate_count = %s, missing_count = %s, status = %s, created_objects = %s, "
                    "completed_at = CASE WHEN %s IN ('READY_FOR_REVIEW', 'COMPLETED') THEN COALESCE(completed_at, now()) ELSE completed_at END, "
                    "updated_at = now() WHERE work_package_id = %s",
                    (
                        generated,
                        valid,
                        invalid,
                        duplicates,
                        missing,
                        status,
                        Jsonb([str(item["workload_object_id"]) for item in objects]),
                        status,
                        package["work_package_id"],
                    ),
                )
                if status in {"READY_FOR_REVIEW", "COMPLETED"} and status != package["status"]:
                    self._audit_with_connection(
                        connection,
                        workload,
                        "WORK_PACKAGE_COMPLETED",
                        {
                            "package_code": package["package_code"],
                            "status": status,
                            "requested": package["requested_count"],
                            "valid": valid,
                        },
                        package_id=str(package["work_package_id"]),
                    )
                connection.commit()

    def progress(self, workload_id: str) -> dict[str, Any]:
        workload = self.get_workload(workload_id)
        tracked = self.progress_tracker.calculate(workload, workload["work_packages"])
        return {
            "workload_id": workload["workload_id"],
            "title": workload["title"],
            "workload_type": workload["workload_type"],
            "status": workload["status"],
            "requested": workload["requested_total"],
            "generated": workload["generated_count"],
            "valid": workload["valid_count"],
            "invalid": workload["invalid_count"],
            "duplicates": workload["duplicate_count"],
            "missing": workload["missing_count"],
            "warnings": tracked["warnings"],
            "errors": tracked["errors"],
            "percent": tracked["percent"],
            "attempts": workload["attempts"],
            "max_generation_attempts": workload["max_generation_attempts"],
            "metrics": workload["metrics"],
            "work_packages": tracked["work_packages"],
            "dependencies": workload["dependencies_resolved"],
        }
