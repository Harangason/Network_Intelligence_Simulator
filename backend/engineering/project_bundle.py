"""Portable, versioned project bundles for explicit browser file storage."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from .db import get_connection
from .models import EngineeringValidationError
from .project_context import normalize_context_project_id
from .workflow.models import default_statuses, default_versions
from .workflow.service import WorkflowStatusService

BUNDLE_VERSION = 2
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")

SOURCE_TABLES = (
    "engineering_hardware_nodes",
    "engineering_hardware_interfaces",
    "engineering_functions",
    "engineering_interfaces",
    "engineering_messages",
    "engineering_signals",
    "engineering_relations",
    "engineering_object_versions",
    "engineering_ai_proposals",
    "engineering_routing_entries",
    "engineering_routing_proposals",
    "engineering_routing_rules",
    "engineering_routing_audit",
)

PROJECT_TABLES = (
    "engineering_analysis_snapshots",
    "engineering_simulation_snapshots",
    "engineering_workflow_events",
    "engineering_optimization_proposals",
    "engineering_intelligence_issue_reviews",
    "engineering_workloads",
    "engineering_work_packages",
    "engineering_workload_objects",
    "engineering_workload_dependencies",
    "engineering_workload_events",
    "engineering_signal_behaviors",
    "engineering_simulation_scenarios",
    "engineering_fault_proposals",
    "engineering_trace_metadata",
    "engineering_simulation_campaigns",
    "engineering_simulation_campaign_runs",
)

PROJECT_TABLES_WITH_PROJECT_ID = {
    "engineering_analysis_snapshots",
    "engineering_simulation_snapshots",
    "engineering_workflow_events",
    "engineering_optimization_proposals",
    "engineering_intelligence_issue_reviews",
    "engineering_workloads",
    "engineering_workload_events",
    "engineering_signal_behaviors",
    "engineering_simulation_scenarios",
    "engineering_fault_proposals",
    "engineering_trace_metadata",
    "engineering_simulation_campaigns",
}

WORKSPACE_RESET_TABLES = (
    "engineering_routing_audit",
    "engineering_routing_rules",
    "engineering_routing_proposals",
    "engineering_routing_entries",
    "engineering_ai_proposals",
    "engineering_object_versions",
    "engineering_relations",
    "engineering_signals",
    "engineering_messages",
    "engineering_interfaces",
    "engineering_hardware_interfaces",
    "engineering_functions",
    "engineering_hardware_nodes",
)

SOURCE_UUID_KEYS = {
    "engineering_hardware_nodes": "id",
    "engineering_hardware_interfaces": "id",
    "engineering_functions": "id",
    "engineering_interfaces": "id",
    "engineering_messages": "id",
    "engineering_signals": "id",
    "engineering_relations": "id",
    "engineering_ai_proposals": "proposal_id",
    "engineering_routing_entries": "id",
    "engineering_routing_proposals": "proposal_id",
    "engineering_routing_rules": "id",
}

PROJECT_UUID_KEYS = {
    "engineering_analysis_snapshots": "id",
    "engineering_simulation_snapshots": "id",
    "engineering_optimization_proposals": "proposal_id",
    "engineering_intelligence_issue_reviews": "issue_review_id",
    "engineering_workloads": "workload_id",
    "engineering_work_packages": "work_package_id",
    "engineering_workload_objects": "workload_object_id",
    "engineering_signal_behaviors": "behavior_id",
    "engineering_simulation_scenarios": "scenario_id",
    "engineering_fault_proposals": "proposal_id",
    "engineering_trace_metadata": "trace_id",
    "engineering_simulation_campaigns": "campaign_id",
}


def normalize_project_id(value: Any) -> str:
    project_id = normalize_context_project_id(value)
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise EngineeringValidationError(
            "project_id darf nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich enthalten."
        )
    return project_id


def _json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _db_value(value: Any) -> Any:
    return Jsonb(value) if isinstance(value, (dict, list)) else value


def _replace_identifiers(value: Any, identifier_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_identifiers(item, identifier_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_identifiers(item, identifier_map) for item in value]
    if isinstance(value, tuple):
        return [_replace_identifiers(item, identifier_map) for item in value]
    return identifier_map.get(str(value), value) if value is not None else None


def _project_rows(connection, table: str, project_id: str) -> list[dict[str, Any]]:
    if table in PROJECT_TABLES_WITH_PROJECT_ID:
        query = sql.SQL("SELECT * FROM {} WHERE project_id = %s ORDER BY 1").format(
            sql.Identifier(table)
        )
    elif table in {"engineering_work_packages", "engineering_workload_objects", "engineering_workload_dependencies"}:
        query = sql.SQL(
            "SELECT child.* FROM {} child JOIN engineering_workloads root "
            "ON root.workload_id = child.workload_id WHERE root.project_id = %s ORDER BY 1"
        ).format(sql.Identifier(table))
    elif table == "engineering_simulation_campaign_runs":
        query = sql.SQL(
            "SELECT child.* FROM engineering_simulation_campaign_runs child "
            "JOIN engineering_simulation_campaigns root ON root.campaign_id = child.campaign_id "
            "WHERE root.project_id = %s ORDER BY 1"
        )
    else:  # pragma: no cover - guarded by the static table registry
        raise ValueError(f"Unbekannte Projekttabelle: {table}")
    return [_json_safe(row) for row in connection.execute(query, (project_id,)).fetchall()]


def _delete_project_rows(connection, table: str, project_id: str) -> None:
    if table in PROJECT_TABLES_WITH_PROJECT_ID:
        query = sql.SQL("DELETE FROM {} WHERE project_id = %s").format(sql.Identifier(table))
    elif table in {"engineering_work_packages", "engineering_workload_objects", "engineering_workload_dependencies"}:
        query = sql.SQL(
            "DELETE FROM {} WHERE workload_id IN "
            "(SELECT workload_id FROM engineering_workloads WHERE project_id = %s)"
        ).format(sql.Identifier(table))
    elif table == "engineering_simulation_campaign_runs":
        query = sql.SQL(
            "DELETE FROM engineering_simulation_campaign_runs WHERE campaign_id IN "
            "(SELECT campaign_id FROM engineering_simulation_campaigns WHERE project_id = %s)"
        )
    else:  # pragma: no cover - guarded by the static table registry
        raise ValueError(f"Unbekannte Projekttabelle: {table}")
    connection.execute(query, (project_id,))


def _clone_source_data(
    source_data: dict[str, list[dict[str, Any]]],
    project_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    identifier_map: dict[str, str] = {}
    for table, key in SOURCE_UUID_KEYS.items():
        for row in source_data.get(table) or []:
            current = row.get(key)
            if current:
                identifier_map[str(current)] = str(uuid.uuid4())

    cloned: dict[str, list[dict[str, Any]]] = {}
    for table in SOURCE_TABLES:
        if table == "engineering_routing_audit":
            cloned[table] = []
            continue
        rows: list[dict[str, Any]] = []
        for source_row in source_data.get(table) or []:
            row = _replace_identifiers(source_row, identifier_map)
            row["project_id"] = project_id
            if table == "engineering_object_versions":
                row.pop("id", None)
            rows.append(row)
        cloned[table] = rows
    return cloned, identifier_map


def _clone_project_data(
    project_data: dict[str, list[dict[str, Any]]],
    project_id: str,
    identifier_map: dict[str, str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    combined_map = dict(identifier_map)
    for table, key in PROJECT_UUID_KEYS.items():
        for row in project_data.get(table) or []:
            current = row.get(key)
            if current:
                combined_map[str(current)] = str(uuid.uuid4())

    cloned: dict[str, list[dict[str, Any]]] = {}
    for table in PROJECT_TABLES:
        if table == "engineering_workflow_events":
            cloned[table] = []
            continue
        rows: list[dict[str, Any]] = []
        for source_row in project_data.get(table) or []:
            row = _replace_identifiers(source_row, combined_map)
            if table in PROJECT_TABLES_WITH_PROJECT_ID:
                row["project_id"] = project_id
            if table == "engineering_workload_events":
                row.pop("event_id", None)
            rows.append(row)
        cloned[table] = rows
    return cloned, combined_map


class ProjectBundleService:
    def reset_workspace(self, project_id: str) -> dict[str, Any]:
        target = normalize_project_id(project_id)
        with get_connection() as connection:
            with connection.transaction():
                for table in reversed(PROJECT_TABLES):
                    _delete_project_rows(connection, table, target)
                for table in WORKSPACE_RESET_TABLES:
                    connection.execute(
                        sql.SQL("DELETE FROM {} WHERE project_id = %s").format(sql.Identifier(table)),
                        (target,),
                    )
                connection.execute("DELETE FROM engineering_workflow_projects WHERE project_id = %s", (target,))
        return {
            "project_id": target,
            "cleared_tables": [*WORKSPACE_RESET_TABLES, *PROJECT_TABLES],
            "workflow": WorkflowStatusService(target).get(),
        }

    def export(self, project_id: str, *, target_project_id: str | None = None) -> dict[str, Any]:
        source_project_id = normalize_project_id(project_id)
        target = normalize_project_id(target_project_id) if target_project_id else source_project_id
        source_state = WorkflowStatusService(source_project_id).get()
        workflow = {
            "project_id": target,
            "active_step": source_state["active_step"],
            "versions": source_state["versions"],
            "statuses": source_state["statuses"],
            "stale_reasons": source_state["stale_reasons"],
            "context": {**source_state["context"], "active_project": target},
            "parameters": source_state["parameters"],
            "topology": source_state["topology"],
        }
        with get_connection() as connection:
            source_data = {
                table: [_json_safe(row) for row in connection.execute(
                    sql.SQL("SELECT * FROM {} WHERE project_id = %s ORDER BY 1").format(sql.Identifier(table)),
                    (source_project_id,),
                ).fetchall()]
                for table in SOURCE_TABLES
            }
            project_data = {
                table: _project_rows(connection, table, source_project_id)
                for table in PROJECT_TABLES
            }
        bundle_source_project_id = source_project_id
        if target != source_project_id:
            source_data, identifier_map = _clone_source_data(source_data, target)
            project_data, identifier_map = _clone_project_data(project_data, target, identifier_map)
            workflow = _replace_identifiers(workflow, identifier_map)
            workflow["project_id"] = target
            workflow["context"] = {**(workflow.get("context") or {}), "active_project": target}
            bundle_source_project_id = target
        return {
            "format": "network-intelligence-project",
            "bundle_version": BUNDLE_VERSION,
            "application": "Communication Simulator",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "project_id": target,
            "source_project_id": bundle_source_project_id,
            "engineering_scope": "project-isolated-source-of-truth",
            "workflow": workflow,
            "source_data": source_data,
            "project_data": project_data,
        }

    def import_bundle(self, bundle: dict[str, Any], *, target_project_id: str | None = None) -> dict[str, Any]:
        if bundle.get("format") != "network-intelligence-project":
            raise EngineeringValidationError("Die Datei ist kein Network-Intelligence-Projektpaket.")
        if int(bundle.get("bundle_version") or 0) > BUNDLE_VERSION:
            raise EngineeringValidationError("Das Projektpaket stammt aus einer neueren Anwendungsversion.")
        bundle_project_id = normalize_project_id(bundle.get("project_id"))
        source_project_id = normalize_project_id(bundle.get("source_project_id") or bundle_project_id)
        target = normalize_project_id(target_project_id) if target_project_id else bundle_project_id
        workflow = bundle.get("workflow")
        if not isinstance(workflow, dict):
            raise EngineeringValidationError("workflow fehlt im Projektpaket.")
        workflow = {**workflow, "project_id": target}
        source_data = bundle.get("source_data") or {}
        project_data = bundle.get("project_data") or {}
        if not isinstance(source_data, dict) or not isinstance(project_data, dict):
            raise EngineeringValidationError("source_data und project_data muessen Objekte sein.")
        if target != source_project_id:
            source_data, identifier_map = _clone_source_data(source_data, target)
            project_data, identifier_map = _clone_project_data(project_data, target, identifier_map)
            workflow = _replace_identifiers(workflow, identifier_map)
            workflow["project_id"] = target
            workflow["context"] = {**(workflow.get("context") or {}), "active_project": target}
            source_project_id = target

        report = {"inserted": 0, "existing": 0, "tables": {}}
        with get_connection() as connection:
            self._upsert_workflow(target, workflow, connection=connection)
            for table in SOURCE_TABLES:
                rows = source_data.get(table) or []
                if table == "engineering_routing_entries":
                    rows = sorted(rows, key=lambda row: (str(row.get("route_code") or ""), int(row.get("revision") or 1)))
                inserted, existing = self._insert_rows(
                    connection,
                    table,
                    rows,
                    preserve_ids=True,
                    project_id=target,
                )
                report["inserted"] += inserted
                report["existing"] += existing
                report["tables"][table] = {"inserted": inserted, "existing": existing}

            preserve_ids = target == source_project_id
            analysis_map: dict[str, str] = {}
            analysis_rows = project_data.get("engineering_analysis_snapshots") or []
            if preserve_ids:
                inserted, existing = self._insert_rows(connection, "engineering_analysis_snapshots", analysis_rows, preserve_ids=True, project_id=target)
            else:
                inserted = existing = 0
                for row in analysis_rows:
                    old_id = str(row.get("id"))
                    new_row = {key: value for key, value in row.items() if key != "id"}
                    new_row["project_id"] = target
                    created = self._insert_row_returning_id(connection, "engineering_analysis_snapshots", new_row)
                    analysis_map[old_id] = created
                    inserted += 1
            report["inserted"] += inserted
            report["existing"] += existing
            report["tables"]["engineering_analysis_snapshots"] = {"inserted": inserted, "existing": existing}

            simulation_rows = project_data.get("engineering_simulation_snapshots") or []
            if not preserve_ids:
                simulation_rows = [
                    {
                        **{key: value for key, value in row.items() if key != "id"},
                        "project_id": target,
                        "validation_snapshot_id": analysis_map.get(str(row.get("validation_snapshot_id"))) if row.get("validation_snapshot_id") else None,
                    }
                    for row in simulation_rows
                ]
            inserted, existing = self._insert_rows(connection, "engineering_simulation_snapshots", simulation_rows, preserve_ids=preserve_ids, project_id=target)
            report["inserted"] += inserted
            report["existing"] += existing
            report["tables"]["engineering_simulation_snapshots"] = {"inserted": inserted, "existing": existing}

            for table in ("engineering_workflow_events", "engineering_optimization_proposals"):
                rows = project_data.get(table) or []
                if not preserve_ids:
                    identifier = "proposal_id" if table == "engineering_optimization_proposals" else "id"
                    rows = [
                        {
                            **{key: value for key, value in row.items() if key != identifier},
                            "project_id": target,
                            **({"source_snapshot_id": analysis_map.get(str(row.get("source_snapshot_id")))} if table == "engineering_optimization_proposals" and row.get("source_snapshot_id") else {}),
                        }
                        for row in rows
                    ]
                inserted, existing = self._insert_rows(connection, table, rows, preserve_ids=preserve_ids, project_id=target)
                report["inserted"] += inserted
                report["existing"] += existing
                report["tables"][table] = {"inserted": inserted, "existing": existing}
            handled_tables = {
                "engineering_analysis_snapshots",
                "engineering_simulation_snapshots",
                "engineering_workflow_events",
                "engineering_optimization_proposals",
            }
            for table in PROJECT_TABLES:
                if table in handled_tables:
                    continue
                rows = project_data.get(table) or []
                inserted, existing = self._insert_rows(
                    connection,
                    table,
                    rows,
                    preserve_ids=preserve_ids,
                    project_id=target if table in PROJECT_TABLES_WITH_PROJECT_ID else None,
                )
                report["inserted"] += inserted
                report["existing"] += existing
                report["tables"][table] = {"inserted": inserted, "existing": existing}
            self._refresh_sequences(connection)
        return {
            "project_id": target,
            "bundle_version": BUNDLE_VERSION,
            "merge_policy": "existing-source-of-truth-preserved",
            "report": report,
            "workflow": WorkflowStatusService(target).get(),
        }

    @staticmethod
    def _upsert_workflow(project_id: str, workflow: dict[str, Any], *, connection=None) -> None:
        if connection is None:
            with get_connection() as owned_connection:
                ProjectBundleService._upsert_workflow(
                    project_id, workflow, connection=owned_connection
                )
            return
        connection.execute(
            """
            INSERT INTO engineering_workflow_projects
                (project_id, active_step, versions, statuses, stale_reasons, context, parameters, topology)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id) DO UPDATE SET
                active_step = EXCLUDED.active_step,
                versions = EXCLUDED.versions,
                statuses = EXCLUDED.statuses,
                stale_reasons = EXCLUDED.stale_reasons,
                context = EXCLUDED.context,
                parameters = EXCLUDED.parameters,
                topology = EXCLUDED.topology,
                updated_at = now()
            """,
            (
                project_id,
                workflow.get("active_step") or "engineering_model",
                Jsonb({**default_versions(), **(workflow.get("versions") or {})}),
                Jsonb({**default_statuses(), **(workflow.get("statuses") or {})}),
                Jsonb(workflow.get("stale_reasons") or {}),
                Jsonb({**(workflow.get("context") or {}), "active_project": project_id}),
                Jsonb(workflow.get("parameters") or {}),
                Jsonb(workflow.get("topology") or {}),
            ),
        )

    @staticmethod
    def _insert_row_returning_id(connection, table: str, row: dict[str, Any]) -> str:
        columns = list(row)
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() * len(columns)),
        )
        created = connection.execute(query, [_db_value(row[column]) for column in columns]).fetchone()
        return str(created["id"])

    @staticmethod
    def _insert_rows(
        connection,
        table: str,
        rows: list[dict[str, Any]],
        *,
        preserve_ids: bool,
        project_id: str | None = None,
    ) -> tuple[int, int]:
        if table not in {*SOURCE_TABLES, *PROJECT_TABLES}:
            raise EngineeringValidationError("Unbekannte Tabelle im Projektpaket.")
        inserted = existing = 0
        for source_row in rows:
            if not isinstance(source_row, dict) or not source_row:
                continue
            row = dict(source_row)
            if project_id:
                row["project_id"] = project_id
            if not preserve_ids:
                row.pop("id", None)
                row.pop("proposal_id", None)
            columns = list(row)
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING RETURNING 1").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.Placeholder() * len(columns)),
            )
            created = connection.execute(query, [_db_value(row[column]) for column in columns]).fetchone()
            if created:
                inserted += 1
            else:
                existing += 1
        return inserted, existing

    @staticmethod
    def _refresh_sequences(connection) -> None:
        for table in (
            "engineering_object_versions",
            "engineering_routing_audit",
            "engineering_workflow_events",
        ):
            connection.execute(
                sql.SQL(
                    "SELECT setval(pg_get_serial_sequence({}, 'id'), "
                    "GREATEST(COALESCE(MAX(id), 1), 1)) FROM {}"
                ).format(sql.Literal(table), sql.Identifier(table))
            )
