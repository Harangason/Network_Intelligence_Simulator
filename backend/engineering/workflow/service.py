"""Persistent workflow state, provenance snapshots and invalidation rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection
from .models import (
    WORKFLOW_LABELS,
    WORKFLOW_STATUSES,
    WORKFLOW_STEPS,
    default_statuses,
    default_versions,
    normalize_step,
    set_step_status,
    transition_state,
)

DEFAULT_PROJECT_ID = "default"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class WorkflowConflictError(RuntimeError):
    """Raised when a snapshot no longer matches its source versions."""


class WorkflowStatusService:
    def __init__(self, project_id: str = DEFAULT_PROJECT_ID) -> None:
        self.project_id = str(project_id or DEFAULT_PROJECT_ID)

    def _ensure(self, connection) -> None:
        connection.execute(
            """
            INSERT INTO engineering_workflow_projects
                (project_id, versions, statuses, stale_reasons, context, parameters, topology)
            VALUES (%s, %s::jsonb, %s::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)
            ON CONFLICT (project_id) DO NOTHING
            """,
            (self.project_id, _json(default_versions()), _json(default_statuses())),
        )

    @staticmethod
    def _state(row: dict[str, Any]) -> dict[str, Any]:
        context = {
            "selected_object": None,
            "selected_route": None,
            "selected_network": None,
            "selected_signal": None,
            "selected_simulation": None,
            **(row.get("context") or {}),
            "active_project": row["project_id"],
            "active_workflow_step": row["active_step"],
        }
        return {
            "project_id": row["project_id"],
            "active_step": row["active_step"],
            "versions": {**default_versions(), **(row.get("versions") or {})},
            "statuses": {**default_statuses(), **(row.get("statuses") or {})},
            "stale_reasons": row.get("stale_reasons") or {},
            "context": context,
            "parameters": row.get("parameters") or {},
            "topology": row.get("topology") or {},
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        }

    def _get_locked(self, connection) -> dict[str, Any]:
        self._ensure(connection)
        row = connection.execute(
            "SELECT * FROM engineering_workflow_projects WHERE project_id = %s FOR UPDATE",
            (self.project_id,),
        ).fetchone()
        return self._state(row)

    def get(self) -> dict[str, Any]:
        with get_connection() as connection:
            self._ensure(connection)
            row = connection.execute(
                "SELECT * FROM engineering_workflow_projects WHERE project_id = %s",
                (self.project_id,),
            ).fetchone()
            state = self._state(row)
            self._bootstrap_statuses(connection, state)
            latest = connection.execute(
                """
                SELECT id, analysis_type, status, is_outdated, outdated_reason, created_at
                FROM engineering_analysis_snapshots
                WHERE project_id = %s
                ORDER BY created_at DESC
                """,
                (self.project_id,),
            ).fetchall()
            simulations = connection.execute(
                """
                SELECT id, source_versions, validation_snapshot_id, calculated_metrics,
                       status, job_id, result,
                       is_outdated, outdated_reason, created_at
                FROM engineering_simulation_snapshots
                WHERE project_id = %s ORDER BY created_at DESC LIMIT 20
                """,
                (self.project_id,),
            ).fetchall()
        latest_by_type: dict[str, dict[str, Any]] = {}
        for item in latest:
            latest_by_type.setdefault(item["analysis_type"], self._serialize_row(item))
        state.update(
            {
                "steps": [
                    {
                        "id": step,
                        "position": index + 1,
                        "label": WORKFLOW_LABELS[step],
                        "status": state["statuses"][step],
                        "version": state["versions"][step],
                        "reason": state["stale_reasons"].get(step),
                    }
                    for index, step in enumerate(WORKFLOW_STEPS)
                ],
                "latest_analyses": latest_by_type,
                "simulation_snapshots": [self._serialize_row(item) for item in simulations],
                "status_vocabulary": list(WORKFLOW_STATUSES),
                "rule": "Define -> Route -> Connect -> Configure -> Calculate -> Validate -> Simulate -> Analyze -> Assess -> Learn -> Improve",
            }
        )
        return state

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        value = dict(row)
        for key, item in list(value.items()):
            if hasattr(item, "isoformat"):
                value[key] = item.isoformat()
            elif item is not None and key.endswith("id"):
                value[key] = str(item)
        return value

    def _bootstrap_statuses(self, connection, state: dict[str, Any]) -> None:
        """Reflect pre-workflow data without inventing source versions."""
        changed = False
        statuses = state["statuses"]
        if statuses["engineering_model"] == "EMPTY":
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM engineering_hardware_nodes"
            ).fetchone()["count"]
            if count:
                statuses["engineering_model"] = "COMPLETE"
                changed = True
        if statuses["routing"] == "EMPTY":
            counts = connection.execute(
                """
                SELECT COUNT(*) AS count,
                       COUNT(*) FILTER (WHERE approval_state = 'APPROVED') AS approved
                FROM engineering_routing_entries
                WHERE status NOT IN ('SUPERSEDED', 'DEPRECATED', 'REJECTED')
                """
            ).fetchone()
            if counts["count"]:
                statuses["routing"] = "APPROVED" if counts["approved"] else "WARNING"
                changed = True
        if statuses["network_editor"] == "EMPTY":
            relation_count = connection.execute(
                "SELECT COUNT(*) AS count FROM engineering_relations WHERE relation_type = 'CONNECTED_TO'"
            ).fetchone()["count"]
            if relation_count or (state.get("topology") or {}).get("nodes"):
                statuses["network_editor"] = "COMPLETE"
                changed = True
        if changed:
            connection.execute(
                "UPDATE engineering_workflow_projects SET statuses = %s::jsonb, updated_at = now() WHERE project_id = %s",
                (_json(statuses), self.project_id),
            )

    def mark_changed(
        self,
        step: str,
        reason: str,
        *,
        status: str = "COMPLETE",
        actor: str | None = None,
    ) -> dict[str, Any]:
        normalize_step(step)
        reason = str(reason or f"{WORKFLOW_LABELS[step]} wurde geaendert.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            next_state = transition_state(state, step, reason, status=status)
            connection.execute(
                """
                UPDATE engineering_workflow_projects
                SET active_step = %s, versions = %s::jsonb, statuses = %s::jsonb,
                    stale_reasons = %s::jsonb, updated_at = now()
                WHERE project_id = %s
                """,
                (
                    step,
                    _json(next_state["versions"]),
                    _json(next_state["statuses"]),
                    _json(next_state["stale_reasons"]),
                    self.project_id,
                ),
            )
            changed_index = WORKFLOW_STEPS.index(step)
            analysis_types = []
            if changed_index < WORKFLOW_STEPS.index("capacity_timing"):
                analysis_types.append("capacity_timing")
            if changed_index < WORKFLOW_STEPS.index("validation"):
                analysis_types.append("preflight")
            if analysis_types:
                connection.execute(
                    """
                    UPDATE engineering_analysis_snapshots
                    SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s
                    WHERE project_id = %s AND analysis_type = ANY(%s) AND is_outdated = FALSE
                    """,
                    (reason, self.project_id, analysis_types),
                )
            if changed_index < WORKFLOW_STEPS.index("simulation"):
                connection.execute(
                    """
                    UPDATE engineering_simulation_snapshots
                    SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s, updated_at = now()
                    WHERE project_id = %s AND is_outdated = FALSE
                    """,
                    (reason, self.project_id),
                )
            if changed_index < WORKFLOW_STEPS.index("data_science_intelligence"):
                connection.execute(
                    """
                    UPDATE engineering_analysis_snapshots
                    SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s
                    WHERE project_id = %s AND analysis_type = 'intelligence' AND is_outdated = FALSE
                    """,
                    (reason, self.project_id),
                )
            connection.execute(
                """
                INSERT INTO engineering_workflow_events
                    (project_id, step, event_type, reason, source_versions, actor)
                VALUES (%s, %s, 'CHANGED', %s, %s::jsonb, %s)
                """,
                (self.project_id, step, reason, _json(next_state["versions"]), actor),
            )
        return self.get()

    def set_context(self, context: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "active_workflow_step",
            "selected_object",
            "selected_route",
            "selected_network",
            "selected_signal",
            "selected_simulation",
        }
        cleaned = {key: value for key, value in context.items() if key in allowed}
        active_step = cleaned.get("active_workflow_step")
        if active_step:
            normalize_step(str(active_step))
        with get_connection() as connection:
            state = self._get_locked(connection)
            merged = {**state["context"], **cleaned, "active_project": self.project_id}
            connection.execute(
                """
                UPDATE engineering_workflow_projects
                SET active_step = %s, context = %s::jsonb, updated_at = now()
                WHERE project_id = %s
                """,
                (active_step or state["active_step"], _json(merged), self.project_id),
            )
        return self.get()

    def save_parameters(self, parameters: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters muss ein nicht-leeres Objekt sein.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            unchanged = state["parameters"] == parameters
            already_current = state["statuses"]["parameters"] == "COMPLETE"
            if not unchanged:
                connection.execute(
                    "UPDATE engineering_workflow_projects SET parameters = %s::jsonb WHERE project_id = %s",
                    (_json(parameters), self.project_id),
                )
        if unchanged and already_current:
            return self.get()
        return self.mark_changed(
            "parameters",
            "Technologie- oder Timing-Parameter wurden bestaetigt." if unchanged else "Technologie- oder Timing-Parameter wurden geaendert.",
            actor=actor,
        )

    def save_topology(self, topology: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        if not isinstance(topology, dict) or not isinstance(topology.get("nodes"), list):
            raise ValueError("topology.nodes muss eine Liste sein.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            unchanged = state["topology"] == topology
            already_current = state["statuses"]["network_editor"] == "COMPLETE"
            if not unchanged:
                connection.execute(
                    "UPDATE engineering_workflow_projects SET topology = %s::jsonb WHERE project_id = %s",
                    (_json(topology), self.project_id),
                )
        if unchanged and already_current:
            return self.get()
        return self.mark_changed(
            "network_editor",
            "Die technische Netzwerktopologie wurde bestaetigt." if unchanged else "Die technische Netzwerktopologie wurde geaendert.",
            actor=actor,
        )

    def create_analysis_snapshot(
        self,
        analysis_type: str,
        *,
        input_data: dict[str, Any],
        results: dict[str, Any],
        findings: list[dict[str, Any]],
        provenance: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        if analysis_type not in {"capacity_timing", "preflight", "intelligence"}:
            raise ValueError("Unbekannter Analysetyp.")
        step = {
            "capacity_timing": "capacity_timing",
            "preflight": "validation",
            "intelligence": "data_science_intelligence",
        }[analysis_type]
        with get_connection() as connection:
            state = self._get_locked(connection)
            reason = {
                "capacity_timing": "Capacity & Timing wurde neu berechnet.",
                "preflight": "Validation / Preflight wurde neu ausgefuehrt.",
                "intelligence": "Data Science & Intelligence wurde neu bewertet.",
            }[analysis_type]
            next_state = transition_state(state, step, reason, status=status)
            connection.execute(
                """
                UPDATE engineering_analysis_snapshots
                SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s
                WHERE project_id = %s AND analysis_type = %s AND is_outdated = FALSE
                """,
                ("Durch einen neueren Snapshot ersetzt.", self.project_id, analysis_type),
            )
            if analysis_type == "capacity_timing":
                connection.execute(
                    """
                    UPDATE engineering_analysis_snapshots
                    SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s
                    WHERE project_id = %s AND analysis_type = 'preflight' AND is_outdated = FALSE
                    """,
                    (reason, self.project_id),
                )
            connection.execute(
                """
                UPDATE engineering_simulation_snapshots
                SET is_outdated = TRUE, status = 'OUTDATED', outdated_reason = %s, updated_at = now()
                WHERE project_id = %s AND is_outdated = FALSE
                """,
                (reason, self.project_id),
            )
            row = connection.execute(
                """
                INSERT INTO engineering_analysis_snapshots
                    (project_id, analysis_type, source_versions, input_data, results,
                     findings, provenance, status)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    self.project_id,
                    analysis_type,
                    _json(next_state["versions"]),
                    _json(input_data),
                    _json(results),
                    _json(findings),
                    _json({**provenance, "timestamp": provenance.get("timestamp") or _now()}),
                    status,
                ),
            ).fetchone()
            connection.execute(
                """
                UPDATE engineering_workflow_projects
                SET versions = %s::jsonb, statuses = %s::jsonb,
                    stale_reasons = %s::jsonb, active_step = %s, updated_at = now()
                WHERE project_id = %s
                """,
                (
                    _json(next_state["versions"]),
                    _json(next_state["statuses"]),
                    _json(next_state["stale_reasons"]),
                    step,
                    self.project_id,
                ),
            )
        return self._serialize_row(row)

    def latest_analysis(self, analysis_type: str, *, include_outdated: bool = False) -> dict[str, Any] | None:
        query = """
            SELECT * FROM engineering_analysis_snapshots
            WHERE project_id = %s AND analysis_type = %s
        """
        if not include_outdated:
            query += " AND is_outdated = FALSE"
        query += " ORDER BY created_at DESC LIMIT 1"
        with get_connection() as connection:
            self._ensure(connection)
            row = connection.execute(query, (self.project_id, analysis_type)).fetchone()
        return self._serialize_row(row) if row else None

    def create_simulation_snapshot(self, configuration: dict[str, Any]) -> dict[str, Any]:
        validation = self.latest_analysis("preflight")
        if not validation or validation["status"] not in {"COMPLETE", "APPROVED", "WARNING"}:
            raise WorkflowConflictError("Ein aktueller, erfolgreicher Preflight ist erforderlich.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            validation_sources = validation["source_versions"]
            if any(
                validation_sources.get(step) != state["versions"].get(step)
                for step in WORKFLOW_STEPS[: WORKFLOW_STEPS.index("simulation")]
            ):
                raise WorkflowConflictError("Der Preflight passt nicht mehr zu den aktuellen Quelldaten.")
            capacity = self.latest_analysis("capacity_timing") or {}
            next_versions = dict(state["versions"])
            next_versions["simulation"] = int(next_versions.get("simulation", 0)) + 1
            next_statuses = dict(state["statuses"])
            next_statuses["simulation"] = "IN_PROGRESS"
            row = connection.execute(
                """
                INSERT INTO engineering_simulation_snapshots
                    (project_id, source_versions, validation_snapshot_id, configuration, calculated_metrics)
                VALUES (%s, %s::jsonb, %s, %s::jsonb, %s::jsonb)
                RETURNING *
                """,
                (
                    self.project_id,
                    _json(next_versions),
                    validation["id"],
                    _json(configuration),
                    _json(capacity.get("results") or {}),
                ),
            ).fetchone()
            connection.execute(
                """
                UPDATE engineering_workflow_projects
                SET versions = %s::jsonb, statuses = %s::jsonb,
                    active_step = 'simulation', updated_at = now()
                WHERE project_id = %s
                """,
                (_json(next_versions), _json(next_statuses), self.project_id),
            )
        return self._serialize_row(row)

    def get_simulation_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with get_connection() as connection:
            self._ensure(connection)
            row = connection.execute(
                "SELECT * FROM engineering_simulation_snapshots WHERE id = %s AND project_id = %s",
                (snapshot_id, self.project_id),
            ).fetchone()
        return self._serialize_row(row) if row else None

    def update_simulation_snapshot(
        self,
        snapshot_id: str,
        *,
        status: str,
        job_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        with get_connection() as connection:
            self._ensure(connection)
            updated = connection.execute(
                """
                UPDATE engineering_simulation_snapshots
                SET status = CASE WHEN is_outdated THEN status ELSE %s END,
                    job_id = COALESCE(%s, job_id),
                    result = CASE WHEN %s::jsonb IS NULL THEN result ELSE %s::jsonb END,
                    updated_at = now()
                WHERE id = %s AND project_id = %s
                RETURNING is_outdated
                """,
                (status, job_id, _json(result) if result is not None else None, _json(result) if result is not None else None, snapshot_id, self.project_id),
            ).fetchone()
            if not updated or updated["is_outdated"]:
                return
            state = self._get_locked(connection)
            next_state = set_step_status(
                state,
                "simulation",
                "COMPLETE" if status == "COMPLETED" else ("ERROR" if status in {"FAILED", "CANCELED"} else "IN_PROGRESS"),
            )
            step = "simulation"
            if status == "COMPLETED":
                next_state = set_step_status(next_state, "results_analysis", "COMPLETE")
                next_state["versions"]["results_analysis"] = int(
                    next_state["versions"].get("results_analysis", 0)
                ) + 1
                if next_state["statuses"].get("data_science_intelligence") != "EMPTY":
                    next_state = set_step_status(
                        next_state,
                        "data_science_intelligence",
                        "OUTDATED",
                        "Neue Simulationsergebnisse muessen in Intelligence neu bewertet werden.",
                    )
                connection.execute(
                    """
                    UPDATE engineering_analysis_snapshots
                    SET is_outdated = TRUE, status = 'OUTDATED',
                        outdated_reason = 'Neue Simulationsergebnisse muessen in Intelligence neu bewertet werden.'
                    WHERE project_id = %s AND analysis_type = 'intelligence' AND is_outdated = FALSE
                    """,
                    (self.project_id,),
                )
                step = "results_analysis"
            connection.execute(
                "UPDATE engineering_workflow_projects SET versions = %s::jsonb, statuses = %s::jsonb, active_step = %s, updated_at = now() WHERE project_id = %s",
                (_json(next_state["versions"]), _json(next_state["statuses"]), step, self.project_id),
            )
