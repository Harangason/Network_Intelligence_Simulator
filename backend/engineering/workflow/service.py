"""Persistent workflow state, provenance snapshots and invalidation rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection
from ..scope_rules import normalize_engineering_scope_rules, scope_placeholder_sql, scope_count_mismatches
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
from ..project_context import activate_project

DEFAULT_PROJECT_ID = "default"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_topology_layout_only_change(current: Any, candidate: Any) -> bool:
    if not isinstance(current, dict) or not isinstance(candidate, dict) or current == candidate:
        return False

    def semantic_view(topology: dict[str, Any]) -> dict[str, Any]:
        nodes = []
        for raw_node in topology.get("nodes", []):
            if not isinstance(raw_node, dict):
                continue
            node = {
                key: value
                for key, value in raw_node.items()
                if key not in {"x", "y", "width", "height", "ports"}
            }
            node["ports"] = sorted(
                (
                    {
                        key: value
                        for key, value in raw_port.items()
                        if key not in {"side", "offset"}
                    }
                    for raw_port in raw_node.get("ports", [])
                    if isinstance(raw_port, dict)
                ),
                key=lambda port: (str(port.get("id", "")), _json(port)),
            )
            nodes.append(node)

        edges = [edge for edge in topology.get("edges", []) if isinstance(edge, dict)]
        return {
            **{key: value for key, value in topology.items() if key not in {"nodes", "edges"}},
            "nodes": sorted(nodes, key=lambda node: (str(node.get("id", "")), _json(node))),
            "edges": sorted(edges, key=lambda edge: (str(edge.get("id", "")), _json(edge))),
        }

    return semantic_view(current) == semantic_view(candidate)


class WorkflowConflictError(RuntimeError):
    """Raised when a snapshot no longer matches its source versions."""


class WorkflowStatusService:
    def __init__(self, project_id: str = DEFAULT_PROJECT_ID) -> None:
        self.project_id = str(project_id or DEFAULT_PROJECT_ID)
        activate_project(self.project_id)

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
        statuses = {**default_statuses(), **(row.get("statuses") or {})}
        stale_reasons = {
            step: reason
            for step, reason in (row.get("stale_reasons") or {}).items()
            if statuses.get(step) in {"OUTDATED", "ERROR"}
        }
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
            "statuses": statuses,
            "stale_reasons": stale_reasons,
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

    def get(self, *, summary: bool = False) -> dict[str, Any]:
        with get_connection() as connection:
            self._ensure(connection)
            row = connection.execute(
                "SELECT * FROM engineering_workflow_projects WHERE project_id = %s",
                (self.project_id,),
            ).fetchone()
            state = self._state(row)
            artifact_checks = self._bootstrap_statuses(connection, state)
            latest = connection.execute(
                """
                SELECT id, analysis_type, status, is_outdated, outdated_reason, created_at
                FROM engineering_analysis_snapshots
                WHERE project_id = %s
                ORDER BY created_at DESC
                """,
                (self.project_id,),
            ).fetchall()
            simulations = []
            if not summary:
                simulations = self._list_simulation_snapshot_rows(connection, include_details=False)
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
                "artifact_checks": artifact_checks,
                "rule": "Define -> Route -> Connect -> Configure -> Calculate -> Validate -> Simulate -> Analyze -> Assess -> Learn -> Improve",
            }
        )
        if summary:
            state["parameters"] = {}
            state["topology"] = {}
        return state

    def _list_simulation_snapshot_rows(self, connection, *, include_details: bool) -> list[dict[str, Any]]:
        detail_columns = ", configuration, calculated_metrics, result" if include_details else ""
        return connection.execute(
            f"""
            SELECT id, source_versions, validation_snapshot_id,
                   status, job_id, is_outdated, outdated_reason, created_at{detail_columns}
            FROM engineering_simulation_snapshots
            WHERE project_id = %s ORDER BY created_at DESC LIMIT 20
            """,
            (self.project_id,),
        ).fetchall()

    def list_simulation_snapshots(self, *, include_details: bool = False) -> list[dict[str, Any]]:
        with get_connection() as connection:
            self._ensure(connection)
            rows = self._list_simulation_snapshot_rows(connection, include_details=include_details)
        return [self._serialize_row(item) for item in rows]

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        value = dict(row)
        for key, item in list(value.items()):
            if hasattr(item, "isoformat"):
                value[key] = item.isoformat()
            elif item is not None and key.endswith("id"):
                value[key] = str(item)
        return value

    def _model_artifact_check(self, connection) -> dict[str, Any]:
        placeholder = scope_placeholder_sql("h")
        count_queries = {
            "hardware_nodes": (
                "SELECT COUNT(*) AS count FROM engineering_hardware_nodes h "
                f"WHERE h.project_id = %s AND NOT {placeholder}"
            ),
            "functions": (
                "SELECT COUNT(*) AS count FROM engineering_functions f "
                "JOIN engineering_hardware_nodes h ON h.id = f.hardware_node_id AND h.project_id = f.project_id "
                f"WHERE f.project_id = %s AND NOT {placeholder}"
            ),
            "interfaces": (
                "SELECT COUNT(*) AS count FROM engineering_interfaces i "
                "JOIN engineering_hardware_nodes h ON h.id = i.hardware_node_id AND h.project_id = i.project_id "
                f"WHERE i.project_id = %s AND NOT {placeholder}"
            ),
            "messages": (
                "SELECT COUNT(*) AS count FROM engineering_messages m "
                "JOIN engineering_interfaces i ON i.id = m.interface_id AND i.project_id = m.project_id "
                "JOIN engineering_hardware_nodes h ON h.id = i.hardware_node_id AND h.project_id = i.project_id "
                f"WHERE m.project_id = %s AND NOT {placeholder}"
            ),
            "signals": (
                "SELECT COUNT(*) AS count FROM engineering_signals s "
                "JOIN engineering_messages m ON m.id = s.message_id AND m.project_id = s.project_id "
                "JOIN engineering_interfaces i ON i.id = m.interface_id AND i.project_id = m.project_id "
                "JOIN engineering_hardware_nodes h ON h.id = i.hardware_node_id AND h.project_id = i.project_id "
                f"WHERE s.project_id = %s AND NOT {placeholder}"
            ),
        }
        counts = {
            label: int(
                connection.execute(
                    query,
                    (self.project_id,),
                ).fetchone()["count"]
            )
            for label, query in count_queries.items()
        }
        hardware_by_type = {
            str(item["device_type"]): int(item["count"])
            for item in connection.execute(
                "SELECT h.device_type, COUNT(*) AS count FROM engineering_hardware_nodes h "
                f"WHERE h.project_id = %s AND NOT {placeholder} GROUP BY h.device_type",
                (self.project_id,),
            ).fetchall()
        }
        broken = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM engineering_functions f
                 WHERE f.project_id = %s AND (f.hardware_node_id IS NULL OR NOT EXISTS (
                     SELECT 1 FROM engineering_hardware_nodes n
                     WHERE n.id = f.hardware_node_id AND n.project_id = f.project_id))) AS functions,
                (SELECT COUNT(*) FROM engineering_interfaces i
                 WHERE i.project_id = %s AND (i.hardware_node_id IS NULL OR i.function_id IS NULL
                     OR NOT EXISTS (SELECT 1 FROM engineering_hardware_nodes n
                         WHERE n.id = i.hardware_node_id AND n.project_id = i.project_id)
                     OR NOT EXISTS (SELECT 1 FROM engineering_functions f
                         WHERE f.id = i.function_id AND f.project_id = i.project_id))) AS interfaces,
                (SELECT COUNT(*) FROM engineering_messages m
                 WHERE m.project_id = %s AND (m.interface_id IS NULL OR m.direction IS NULL
                     OR m.cycle_ms IS NULL OR m.dlc IS NULL
                     OR NOT EXISTS (SELECT 1 FROM engineering_interfaces i
                         WHERE i.id = m.interface_id AND i.project_id = m.project_id))) AS messages,
                (SELECT COUNT(*) FROM engineering_signals s
                 WHERE s.project_id = %s AND (s.message_id IS NULL OR s.start_bit IS NULL
                     OR s.length_bits IS NULL OR s.byte_order IS NULL OR s.data_type IS NULL
                     OR s.factor IS NULL OR s.offset_value IS NULL
                     OR NOT EXISTS (SELECT 1 FROM engineering_messages m
                         WHERE m.id = s.message_id AND m.project_id = s.project_id))) AS signals
            """,
            (self.project_id, self.project_id, self.project_id, self.project_id),
        ).fetchone()
        incomplete = {key: int(value or 0) for key, value in broken.items()}
        has_any = any(counts.values())
        complete = all(counts.values()) and not any(incomplete.values())
        return {
            "status": "COMPLETE" if complete else ("IN_PROGRESS" if has_any else "EMPTY"),
            "complete": complete,
            "counts": counts,
            "hardware_by_type": hardware_by_type,
            "incomplete": incomplete,
        }

    def _routing_artifact_check(self, connection) -> dict[str, Any]:
        counts = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE approval_state = 'APPROVED') AS approved,
                   COUNT(*) FILTER (WHERE validation ->> 'valid' = 'true') AS valid,
                   COUNT(*) FILTER (WHERE status = 'CONFLICT') AS conflicts
            FROM engineering_routing_entries
            WHERE project_id = %s
              AND status NOT IN ('SUPERSEDED', 'DEPRECATED', 'REJECTED', 'OUTDATED')
            """,
            (self.project_id,),
        ).fetchone()
        total = int(counts["total"] or 0)
        approved = int(counts["approved"] or 0)
        valid = int(counts["valid"] or 0)
        conflicts = int(counts["conflicts"] or 0)
        complete = total > 0 and approved == total and valid == total
        status = "APPROVED" if complete else (
            "WARNING" if conflicts else ("IN_PROGRESS" if total else "EMPTY")
        )
        return {
            "status": status,
            "complete": complete,
            "counts": {
                "total": total,
                "approved": approved,
                "valid": valid,
                "conflicts": conflicts,
            },
        }

    @staticmethod
    def _topology_artifact_check(topology: dict[str, Any]) -> dict[str, Any]:
        nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
        edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
        node_map = {
            str(node.get("id")): node
            for node in nodes
            if isinstance(node, dict) and node.get("id")
        }
        port_owner: dict[str, str] = {}
        invalid_nodes = 0
        for node_id, node in node_map.items():
            ports = node.get("ports") if isinstance(node.get("ports"), list) else []
            if not node.get("name") or not node.get("kind") or not node.get("engineeringId") or not ports:
                invalid_nodes += 1
            for port in ports:
                if isinstance(port, dict) and port.get("id"):
                    port_owner[str(port["id"])] = node_id
                    if not port.get("engineeringId"):
                        invalid_nodes += 1
                else:
                    invalid_nodes += 1
        invalid_edges = 0
        for edge in edges:
            if not isinstance(edge, dict):
                invalid_edges += 1
                continue
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            source_port = str(edge.get("sourcePort") or "")
            target_port = str(edge.get("targetPort") or "")
            if (
                not edge.get("id")
                or source == target
                or source not in node_map
                or target not in node_map
                or port_owner.get(source_port) != source
                or port_owner.get(target_port) != target
                or not edge.get("engineeringRelationId")
            ):
                invalid_edges += 1
        has_any = bool(nodes or edges)
        complete = (
            len(node_map) >= 2
            and len(edges) >= 1
            and len(node_map) == len(nodes)
            and invalid_nodes == 0
            and invalid_edges == 0
        )
        return {
            "status": "COMPLETE" if complete else ("IN_PROGRESS" if has_any else "EMPTY"),
            "complete": complete,
            "counts": {"nodes": len(nodes), "edges": len(edges)},
            "invalid": {"nodes": invalid_nodes, "edges": invalid_edges},
        }

    @staticmethod
    def _parameter_artifact_check(parameters: dict[str, Any]) -> dict[str, Any]:
        if not parameters:
            return {
                "status": "APPROVED",
                "complete": True,
                "uses_defaults": True,
                "required": {},
                "invalid_numeric": [],
            }
        formats = parameters.get("formats")
        required = {
            "industry": bool(str(parameters.get("industry") or "").strip()),
            "technology": bool(str(parameters.get("technology") or "").strip()),
            "formats": isinstance(formats, list) and bool(formats),
            "bitrate": isinstance(parameters.get("bitrate"), (int, float))
            and float(parameters["bitrate"]) > 0,
            "cycle_ms": isinstance(parameters.get("cycle_ms"), (int, float))
            and float(parameters["cycle_ms"]) > 0,
            "payload_bytes": isinstance(parameters.get("payload_bytes"), (int, float))
            and float(parameters["payload_bytes"]) >= 0,
            "queue_size": isinstance(parameters.get("queue_size"), (int, float))
            and float(parameters["queue_size"]) > 0,
        }
        invalid_numeric = [
            key
            for key, value in parameters.items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (value < 0 or (key in {"bitrate", "cycle_ms", "duration_s"} and value <= 0))
        ]
        thresholds = [
            parameters.get("warning_threshold"),
            parameters.get("critical_threshold"),
            parameters.get("overload_threshold"),
        ]
        thresholds_valid = all(isinstance(value, (int, float)) for value in thresholds) and (
            0 <= float(thresholds[0]) < float(thresholds[1]) < float(thresholds[2]) <= 100
        )
        required["load_thresholds"] = thresholds_valid
        target_bus_load = parameters.get("target_bus_load_percent", 60)
        required["target_bus_load"] = (
            isinstance(target_bus_load, (int, float))
            and not isinstance(target_bus_load, bool)
            and 0 <= float(target_bus_load) <= 100
        )
        complete = all(required.values()) and not invalid_numeric
        return {
            "status": "APPROVED" if complete else "IN_PROGRESS",
            "complete": complete,
            "uses_defaults": False,
            "required": required,
            "invalid_numeric": invalid_numeric,
        }

    def _source_artifact_check(
        self,
        connection,
        step: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if step == "engineering_model":
            check = self._model_artifact_check(connection)
            mismatches = scope_count_mismatches(check["hardware_by_type"],
                                                (state.get("context") or {}).get("engineering_scope_rules"))
            check["scope_mismatches"] = mismatches
            if mismatches:
                check["complete"] = False
                if check["status"] == "COMPLETE":
                    check["status"] = "IN_PROGRESS"
            return check
        if step == "routing":
            return self._routing_artifact_check(connection)
        if step == "network_editor":
            return self._topology_artifact_check(state.get("topology") or {})
        if step == "parameters":
            return self._parameter_artifact_check(state.get("parameters") or {})
        raise ValueError(f"Kein Quellen-Artefaktcheck fuer {step!r}.")

    def _bootstrap_statuses(self, connection, state: dict[str, Any]) -> dict[str, Any]:
        """Reconcile source statuses with real, project-scoped artifacts."""
        statuses = state["statuses"]
        checks: dict[str, Any] = {}
        changed = False
        for step in WORKFLOW_STEPS[:4]:
            check = self._source_artifact_check(connection, step, state)
            checks[step] = check
            if statuses.get(step) == "OUTDATED" and step != "parameters":
                continue
            expected = check["status"]
            previous = statuses.get(step)
            if previous != expected:
                statuses[step] = expected
                changed = True
                if previous in {"COMPLETE", "APPROVED"} and expected not in {"COMPLETE", "APPROVED"}:
                    reason = f"{WORKFLOW_LABELS[step]} besitzt kein vollstaendiges Artefakt mehr."
                    for dependent in WORKFLOW_STEPS[WORKFLOW_STEPS.index(step) + 1 :]:
                        if statuses.get(dependent) != "EMPTY":
                            statuses[dependent] = "OUTDATED"
                            state["stale_reasons"][dependent] = reason
        if changed:
            connection.execute(
                "UPDATE engineering_workflow_projects SET statuses = %s::jsonb, "
                "stale_reasons = %s::jsonb, updated_at = now() WHERE project_id = %s",
                (_json(statuses), _json(state["stale_reasons"]), self.project_id),
            )
        return checks

    def artifact_status(self, step: str) -> dict[str, Any]:
        if step not in WORKFLOW_STEPS[:4]:
            raise ValueError("artifact_status ist nur fuer Quellschritte verfuegbar.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            return self._source_artifact_check(connection, step, state)

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
            if step in WORKFLOW_STEPS[:4] and status not in {"OUTDATED", "ERROR"}:
                status = self._source_artifact_check(connection, step, state)["status"]
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

    def set_context(self, context: dict[str, Any], *, summary: bool = False) -> dict[str, Any]:
        allowed = {
            "agent_execution",
            "agent_wizard_status",
            "active_workflow_step",
            "engineering_scope_rules",
            "selected_object",
            "selected_route",
            "selected_network",
            "selected_signal",
            "selected_simulation",
        }
        cleaned = {key: value for key, value in context.items() if key in allowed}
        if "engineering_scope_rules" in cleaned:
            cleaned["engineering_scope_rules"] = normalize_engineering_scope_rules(
                cleaned["engineering_scope_rules"]
            )
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
        return self.get(summary=summary)

    def save_parameters(self, parameters: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters muss ein nicht-leeres Objekt sein.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            unchanged = state["parameters"] == parameters
            check = self._parameter_artifact_check(parameters)
            already_current = state["statuses"]["parameters"] == check["status"]
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
            status=check["status"],
            actor=actor,
        )

    def save_topology(self, topology: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        if not isinstance(topology, dict) or not isinstance(topology.get("nodes"), list):
            raise ValueError("topology.nodes muss eine Liste sein.")
        with get_connection() as connection:
            state = self._get_locked(connection)
            unchanged = state["topology"] == topology
            layout_only = is_topology_layout_only_change(state["topology"], topology)
            check = self._topology_artifact_check(topology)
            already_current = state["statuses"]["network_editor"] == check["status"]
            if not unchanged:
                connection.execute(
                    "UPDATE engineering_workflow_projects SET topology = %s::jsonb WHERE project_id = %s",
                    (_json(topology), self.project_id),
                )
        if layout_only:
            return self.get()
        if unchanged and already_current:
            return self.get()
        return self.mark_changed(
            "network_editor",
            "Die technische Netzwerktopologie wurde bestaetigt." if unchanged else "Die technische Netzwerktopologie wurde geaendert.",
            status=check["status"],
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
            if analysis_type in {"capacity_timing", "preflight"}:
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
            next_state = set_step_status(state, "simulation", "IN_PROGRESS")
            next_versions = next_state["versions"]
            next_versions["simulation"] = int(next_versions.get("simulation", 0)) + 1
            connection.execute(
                """
                UPDATE engineering_simulation_snapshots
                SET is_outdated = TRUE, status = 'OUTDATED',
                    outdated_reason = 'Durch einen neueren Simulationslauf ersetzt.',
                    updated_at = now()
                WHERE project_id = %s AND is_outdated = FALSE
                """,
                (self.project_id,),
            )
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
                    stale_reasons = %s::jsonb, active_step = 'simulation', updated_at = now()
                WHERE project_id = %s
                """,
                (
                    _json(next_versions),
                    _json(next_state["statuses"]),
                    _json(next_state["stale_reasons"]),
                    self.project_id,
                ),
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
                RETURNING *
                """,
                (status, job_id, _json(result) if result is not None else None, _json(result) if result is not None else None, snapshot_id, self.project_id),
            ).fetchone()
            if not updated or updated["is_outdated"]:
                return
            state = self._get_locked(connection)
            snapshot_versions = updated.get("source_versions") or {}
            if snapshot_versions.get("simulation") != state["versions"].get("simulation"):
                return
            next_state = set_step_status(
                state,
                "simulation",
                "COMPLETE" if status == "COMPLETED" else ("ERROR" if status in {"FAILED", "CANCELED"} else "IN_PROGRESS"),
            )
            step = "simulation"
            if status == "COMPLETED":
                has_evidence = isinstance(result, dict) and bool(
                    result.get("runtime_metrics")
                    or result.get("trace")
                    or result.get("hardware_validation")
                    or result.get("warnings")
                )
                if has_evidence:
                    next_state = set_step_status(next_state, "results_analysis", "COMPLETE")
                    next_state["versions"]["results_analysis"] = int(
                        next_state["versions"].get("results_analysis", 0)
                    ) + 1
                    connection.execute(
                        """
                        UPDATE engineering_analysis_snapshots
                        SET is_outdated = TRUE, status = 'OUTDATED',
                            outdated_reason = 'Durch eine neuere Ergebnisanalyse ersetzt.'
                        WHERE project_id = %s AND analysis_type = 'results_analysis'
                          AND is_outdated = FALSE
                        """,
                        (self.project_id,),
                    )
                    runtime = result.get("runtime_metrics") or {}
                    warnings = result.get("warnings") or []
                    findings = [
                        {
                            "severity": "WARNING",
                            "code": "SIMULATION_WARNING",
                            "message": str(item),
                        }
                        for item in warnings
                    ]
                    summary = {
                        "simulation_snapshot_id": str(snapshot_id),
                        "job_id": job_id or updated.get("job_id"),
                        "status": status,
                        "runtime_metrics": runtime,
                        "trace": result.get("trace") or {},
                        "hardware_validation": result.get("hardware_validation") or {},
                        "warning_count": len(warnings),
                    }
                    connection.execute(
                        """
                        INSERT INTO engineering_analysis_snapshots
                            (project_id, analysis_type, source_versions, input_data, results,
                             findings, provenance, status)
                        VALUES (%s, 'results_analysis', %s::jsonb, %s::jsonb, %s::jsonb,
                                %s::jsonb, %s::jsonb, 'COMPLETE')
                        """,
                        (
                            self.project_id,
                            _json(next_state["versions"]),
                            _json({
                                "simulation_snapshot_id": str(snapshot_id),
                                "configuration": updated.get("configuration") or {},
                            }),
                            _json(summary),
                            _json(findings),
                            _json({
                                "source": "simulation-service",
                                "job_id": job_id or updated.get("job_id"),
                                "timestamp": _now(),
                            }),
                        ),
                    )
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
                else:
                    next_state = set_step_status(
                        next_state,
                        "results_analysis",
                        "ERROR",
                        "Der Simulator lieferte kein auswertbares Ergebnisartefakt.",
                    )
            connection.execute(
                "UPDATE engineering_workflow_projects SET versions = %s::jsonb, statuses = %s::jsonb, stale_reasons = %s::jsonb, active_step = %s, updated_at = now() WHERE project_id = %s",
                (
                    _json(next_state["versions"]),
                    _json(next_state["statuses"]),
                    _json(next_state["stale_reasons"]),
                    step,
                    self.project_id,
                ),
            )
