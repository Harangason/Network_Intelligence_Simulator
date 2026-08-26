"""Postgres persistence, governance and audit trail for routing aggregates."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from ..db import get_connection
from ..models import EngineeringValidationError, validate_uuid
from ..repository import NotFoundError
from .models import PRIORITIES, PROPOSAL_STATUSES, ROUTE_STATUSES, normalize_route

JSON_FIELDS = ("source", "payload", "destinations", "route", "timing", "routing_policy", "validation")
EDITABLE_FIELDS = (
    "name",
    "description",
    *JSON_FIELDS,
    "status",
    "origin",
    "confidence",
    "review_state",
    "approval_state",
    "source_id",
    "source_version",
)


def _route_code() -> str:
    return f"RT-{uuid.uuid4().hex[:8].upper()}"


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


def _audit(
    connection,
    route_id: str | None,
    action: str,
    *,
    actor: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    evidence: list[Any] | None = None,
    agent: str | None = None,
    model: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO engineering_routing_audit "
        "(route_id, action, actor, agent, model, before_state, after_state, reason, evidence) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            route_id,
            action,
            actor,
            agent,
            model,
            Jsonb(_json_safe(before)) if before is not None else None,
            Jsonb(_json_safe(after)) if after is not None else None,
            reason,
            Jsonb(_json_safe(evidence or [])),
        ),
    )


def _insert_route(
    connection,
    data: dict[str, Any],
    *,
    route_code: str,
    revision: int,
    supersedes_id: str | None = None,
) -> dict[str, Any]:
    columns = [
        "route_code",
        "revision",
        "supersedes_id",
        *EDITABLE_FIELDS,
        "created_by",
        "modified_by",
    ]
    values = [route_code, revision, supersedes_id]
    for field in EDITABLE_FIELDS:
        value = data.get(field)
        values.append(Jsonb(value) if field in JSON_FIELDS else value)
    values.extend((data.get("created_by"), data.get("modified_by")))
    query = sql.SQL("INSERT INTO engineering_routing_entries ({}) VALUES ({}) RETURNING *").format(
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(columns)),
    )
    return connection.execute(query, values).fetchone()


def create_route(data: dict[str, Any]) -> dict[str, Any]:
    if str(data.get("origin") or "MANUAL").upper() == "AI_GENERATED":
        raise EngineeringValidationError("KI-Routen müssen zuerst als RoutingProposal gespeichert werden.")
    if str(data.get("approval_state") or "PENDING").upper() != "PENDING":
        raise EngineeringValidationError("Neue Routen können nicht direkt freigegeben werden.")
    normalized = normalize_route(data)
    normalized["status"] = (
        "PENDING_CONFIRMATION" if normalized["origin"] == "NETWORK_EDITOR" else "DRAFT"
    )
    normalized["approval_state"] = "PENDING"
    with get_connection() as connection:
        row = _insert_route(connection, normalized, route_code=_route_code(), revision=1)
        _audit(connection, str(row["id"]), "ROUTE_CREATED", actor=normalized.get("created_by"), after=row)
        connection.commit()
    return row


def get_route(route_id: str) -> dict[str, Any]:
    validate_uuid(route_id)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM engineering_routing_entries WHERE id = %s", (route_id,)
        ).fetchone()
    if row is None:
        raise NotFoundError(f"RoutingEntry {route_id} nicht gefunden.")
    return row


def list_routes(
    *,
    status: str | None = None,
    approval_state: str | None = None,
    origin: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = []
    values: list[Any] = []
    for column, value in (("status", status), ("approval_state", approval_state), ("origin", origin)):
        if value:
            clauses.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
            values.append(value.upper())
    where = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("")
    query = sql.SQL(
        "SELECT * FROM engineering_routing_entries{} ORDER BY modified_at DESC LIMIT %s OFFSET %s"
    ).format(where)
    values.extend((limit, offset))
    with get_connection() as connection:
        return connection.execute(query, values).fetchall()


def update_route(route_id: str, data: dict[str, Any]) -> dict[str, Any]:
    current = get_route(route_id)
    if "approval_state" in data:
        raise EngineeringValidationError("Freigaben sind nur über den Approval-Endpunkt zulässig.")
    normalized = normalize_route(data, current)
    actor = normalized.get("modified_by")
    if current["approval_state"] == "APPROVED" or current["status"] in (
        "APPROVED",
        "RELEASED",
        "REJECTED",
        "OUTDATED",
    ):
        normalized.update(
            {
                "status": "PENDING_CONFIRMATION"
                if normalized["origin"] == "NETWORK_EDITOR"
                else "DRAFT",
                "approval_state": "PENDING",
                "review_state": "UNREVIEWED",
            }
        )
        normalized["validation"] = {}
        normalized["origin"] = "AI_MODIFIED" if current["origin"] == "AI_GENERATED" else current["origin"]
        with get_connection() as connection:
            row = _insert_route(
                connection,
                normalized,
                route_code=current["route_code"],
                revision=int(current["revision"]) + 1,
                supersedes_id=str(current["id"]),
            )
            _audit(
                connection,
                str(row["id"]),
                "ROUTE_REVISION_CREATED",
                actor=actor,
                before=current,
                after=row,
                reason=data.get("reason"),
            )
            connection.commit()
        return row

    updates = {field: normalized[field] for field in EDITABLE_FIELDS if field in normalized}
    route_changed = any(field in data for field in ("source", "payload", "destinations", "route", "timing", "routing_policy"))
    if route_changed:
        updates.update(
            {
                "validation": {},
                "status": "PENDING_CONFIRMATION"
                if normalized["origin"] == "NETWORK_EDITOR"
                else "DRAFT",
                "review_state": "UNREVIEWED",
            }
        )
    assignments = [sql.SQL("{} = %s").format(sql.Identifier(field)) for field in updates]
    values = [Jsonb(value) if field in JSON_FIELDS else value for field, value in updates.items()]
    values.extend((actor, route_id))
    query = sql.SQL(
        "UPDATE engineering_routing_entries SET {}, revision = revision + 1, "
        "modified_by = %s, modified_at = now() WHERE id = %s RETURNING *"
    ).format(sql.SQL(", ").join(assignments))
    with get_connection() as connection:
        row = connection.execute(query, values).fetchone()
        _audit(connection, route_id, "ROUTE_EDITED", actor=actor, before=current, after=row, reason=data.get("reason"))
        connection.commit()
    return row


def save_validation(route_id: str, validation: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
    current = get_route(route_id)
    if current["status"] in ("REJECTED", "OUTDATED"):
        raise EngineeringValidationError(
            "Abgelehnte oder veraltete Routing-Revisionen sind unveränderliche Historie."
        )
    status = "READY_FOR_REVIEW" if validation.get("valid") else "CONFLICT"
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_routing_entries SET validation = %s, status = %s, "
            "review_state = %s, modified_at = now(), modified_by = %s WHERE id = %s RETURNING *",
            (Jsonb(validation), status, "IN_REVIEW" if validation.get("valid") else "UNREVIEWED", actor, route_id),
        ).fetchone()
        _audit(connection, route_id, "ROUTE_VALIDATED", actor=actor, before=current, after=row, evidence=validation.get("evidence"))
        connection.commit()
    return row


def _publish_graph(connection, route: dict[str, Any], actor: str | None) -> None:
    source_id = route["source"].get("node_id")
    for destination in route["destinations"]:
        target_id = destination.get("node_id")
        if not source_id or not target_id:
            continue
        connection.execute(
            "INSERT INTO engineering_relations "
            "(relation_type, source_type, source_id, target_type, target_id, attributes, source, "
            "provenance, review_state, approval_state, created_by) "
            "VALUES ('ROUTES_TO', 'HardwareNode', %s, 'HardwareNode', %s, %s, 'manual', %s, "
            "'reviewed', 'approved', %s) ON CONFLICT "
            "(relation_type, source_type, source_id, target_type, target_id) "
            "DO UPDATE SET attributes = EXCLUDED.attributes, approval_state = 'approved'",
            (
                source_id,
                target_id,
                Jsonb({"route_id": str(route["id"]), "route_code": route["route_code"]}),
                Jsonb({"origin": "routing-manager"}),
                actor,
            ),
        )
    for signal_id in route["payload"].get("signal_ids", []):
        connection.execute(
            "INSERT INTO engineering_relations "
            "(relation_type, source_type, source_id, target_type, target_id, attributes, source, "
            "provenance, review_state, approval_state, created_by) "
            "VALUES ('USES_ROUTE', 'Signal', %s, 'RoutingEntry', %s, %s, 'manual', %s, "
            "'reviewed', 'approved', %s) ON CONFLICT DO NOTHING",
            (
                signal_id,
                route["id"],
                Jsonb({"route_code": route["route_code"]}),
                Jsonb({"origin": "routing-manager"}),
                actor,
            ),
        )


def approve_routes(route_ids: list[str], *, actor: str | None = None, approve_all_valid: bool = False) -> list[dict[str, Any]]:
    if approve_all_valid:
        with get_connection() as connection:
            route_ids = [
                str(row["id"])
                for row in connection.execute(
                    "SELECT id FROM engineering_routing_entries WHERE validation ->> 'valid' = 'true' "
                    "AND approval_state = 'PENDING'"
                ).fetchall()
            ]
    approved: list[dict[str, Any]] = []
    with get_connection() as connection:
        for route_id in route_ids:
            validate_uuid(route_id)
            current = connection.execute(
                "SELECT * FROM engineering_routing_entries WHERE id = %s FOR UPDATE", (route_id,)
            ).fetchone()
            if current is None:
                raise NotFoundError(f"RoutingEntry {route_id} nicht gefunden.")
            if not current.get("validation", {}).get("valid"):
                raise EngineeringValidationError(
                    f"Route {current['route_code']} ist nicht valide und kann nicht freigegeben werden."
                )
            row = connection.execute(
                "UPDATE engineering_routing_entries SET status = 'APPROVED', review_state = 'REVIEWED', "
                "approval_state = 'APPROVED', approved_by = %s, approved_at = now(), modified_by = %s, "
                "modified_at = now() WHERE id = %s RETURNING *",
                (actor, actor, route_id),
            ).fetchone()
            _publish_graph(connection, row, actor)
            _audit(connection, route_id, "ROUTE_APPROVED", actor=actor, before=current, after=row)
            approved.append(row)
        connection.commit()
    return approved


def reject_routes(route_ids: list[str], *, actor: str | None = None, reason: str | None = None) -> list[dict[str, Any]]:
    rejected = []
    with get_connection() as connection:
        for route_id in route_ids:
            validate_uuid(route_id)
            current = connection.execute(
                "SELECT * FROM engineering_routing_entries WHERE id = %s", (route_id,)
            ).fetchone()
            if current is None:
                raise NotFoundError(f"RoutingEntry {route_id} nicht gefunden.")
            row = connection.execute(
                "UPDATE engineering_routing_entries SET status = 'REJECTED', review_state = 'REJECTED', "
                "approval_state = 'REJECTED', modified_by = %s, modified_at = now() WHERE id = %s RETURNING *",
                (actor, route_id),
            ).fetchone()
            _audit(connection, route_id, "ROUTE_REJECTED", actor=actor, before=current, after=row, reason=reason)
            rejected.append(row)
        connection.commit()
    return rejected


def delete_route(route_id: str, *, actor: str | None = None) -> None:
    current = get_route(route_id)
    if current["approval_state"] == "APPROVED" or current["status"] in ("APPROVED", "RELEASED"):
        raise EngineeringValidationError(
            "Freigegebene Routing-Revisionen dürfen nicht gelöscht werden."
        )
    with get_connection() as connection:
        _audit(connection, route_id, "ROUTE_DELETED", actor=actor, before=current)
        connection.execute("DELETE FROM engineering_routing_entries WHERE id = %s", (route_id,))
        connection.commit()


def create_proposal(data: dict[str, Any]) -> dict[str, Any]:
    prompt = str(data.get("prompt") or "").strip()
    generated_routes = data.get("generated_routes")
    if not prompt or not isinstance(generated_routes, list) or not generated_routes:
        raise EngineeringValidationError("prompt und generated_routes sind erforderlich.")
    with get_connection() as connection:
        row = connection.execute(
            "INSERT INTO engineering_routing_proposals "
            "(prompt, target_objects, generated_routes, retrieved_context, evidence, confidence, "
            "validation_results, model, model_version, status, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'AI_GENERATED', %s) RETURNING *",
            (
                prompt,
                Jsonb(data.get("target_objects", [])),
                Jsonb(generated_routes),
                Jsonb(data.get("retrieved_context", [])),
                Jsonb(data.get("evidence", [])),
                data.get("confidence"),
                Jsonb(data.get("validation_results", [])),
                data.get("model"),
                data.get("model_version"),
                data.get("created_by") or data.get("actor"),
            ),
        ).fetchone()
        _audit(
            connection,
            None,
            "ROUTE_GENERATED_BY_AI",
            actor=data.get("created_by") or data.get("actor"),
            after={"proposal_id": str(row["proposal_id"]), "generated_routes": generated_routes},
            evidence=data.get("evidence"),
            agent="routing-generation-service",
            model=data.get("model"),
        )
        connection.commit()
    return row


def list_proposals(*, status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    values: list[Any] = []
    where = ""
    if status:
        normalized = status.upper()
        if normalized not in PROPOSAL_STATUSES:
            raise EngineeringValidationError(f"Unbekannter Proposal-Status: {status!r}.")
        where = " WHERE status = %s"
        values.append(normalized)
    values.extend((limit, offset))
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_routing_proposals" + where + " ORDER BY created_at DESC LIMIT %s OFFSET %s",
            values,
        ).fetchall()


def get_proposal(proposal_id: str) -> dict[str, Any]:
    validate_uuid(proposal_id)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM engineering_routing_proposals WHERE proposal_id = %s", (proposal_id,)
        ).fetchone()
    if row is None:
        raise NotFoundError(f"RoutingProposal {proposal_id} nicht gefunden.")
    return row


def update_proposal(proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
    current = get_proposal(proposal_id)
    status = str(data.get("status") or current["status"]).upper()
    if status not in PROPOSAL_STATUSES:
        raise EngineeringValidationError(f"Unbekannter Proposal-Status: {status!r}.")
    generated_routes = data.get("generated_routes", current["generated_routes"])
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_routing_proposals SET generated_routes = %s, status = %s, "
            "modified_by = %s, modified_at = now() WHERE proposal_id = %s RETURNING *",
            (Jsonb(generated_routes), status, data.get("actor"), proposal_id),
        ).fetchone()
        connection.commit()
    return row


def delete_proposal(proposal_id: str, *, actor: str | None = None) -> None:
    current = get_proposal(proposal_id)
    if current["status"] == "APPROVED":
        raise EngineeringValidationError("Übernommene Routing-Proposals dürfen nicht gelöscht werden.")
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM engineering_routing_proposals WHERE proposal_id = %s", (proposal_id,)
        )
        _audit(
            connection,
            None,
            "ROUTING_PROPOSAL_DELETED",
            actor=actor,
            before={"proposal_id": proposal_id, "status": current["status"]},
        )
        connection.commit()


def accept_proposal_routes(proposal_id: str, indexes: list[int], *, actor: str | None = None) -> list[dict[str, Any]]:
    proposal = get_proposal(proposal_id)
    routes = proposal["generated_routes"]
    selected = indexes if indexes else list(range(len(routes)))
    created = []
    for index in selected:
        if index < 0 or index >= len(routes):
            raise EngineeringValidationError(f"Ungültiger Routenvorschlagsindex: {index}.")
        payload = {**routes[index], "origin": "AI_GENERATED", "confidence": proposal.get("confidence"), "actor": actor}
        # Human acceptance creates a draft, never an approved route.
        normalized = normalize_route(payload)
        normalized.update({"status": "DRAFT", "approval_state": "PENDING", "review_state": "UNREVIEWED"})
        with get_connection() as connection:
            row = _insert_route(connection, normalized, route_code=_route_code(), revision=1)
            _audit(connection, str(row["id"]), "ROUTE_PROPOSAL_ACCEPTED_AS_DRAFT", actor=actor, after=row)
            connection.commit()
        created.append(row)
    update_proposal(
        proposal_id,
        {"status": "PARTIALLY_APPROVED" if len(selected) < len(routes) else "APPROVED", "actor": actor},
    )
    return created


def list_audit_events(route_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    values: list[Any] = []
    where = ""
    if route_id:
        validate_uuid(route_id)
        where = " WHERE route_id = %s"
        values.append(route_id)
    values.append(limit)
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_routing_audit" + where + " ORDER BY occurred_at DESC LIMIT %s",
            values,
        ).fetchall()


def list_route_versions(route_code: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_routing_entries WHERE route_code = %s ORDER BY revision DESC",
            (route_code,),
        ).fetchall()


def _normalize_rule(data: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**(current or {}), **data}
    name = str(merged.get("name") or "").strip()
    condition = merged.get("condition")
    action = merged.get("action")
    priority = str(merged.get("priority") or "NORMAL").upper()
    status = str(merged.get("status") or "DRAFT").upper()
    if not name:
        raise EngineeringValidationError("RoutingRule.name ist erforderlich.")
    if not isinstance(condition, dict) or not condition:
        raise EngineeringValidationError("RoutingRule.condition muss ein nicht-leeres Objekt sein.")
    if not isinstance(action, dict) or not action:
        raise EngineeringValidationError("RoutingRule.action muss ein nicht-leeres Objekt sein.")
    if priority not in PRIORITIES:
        raise EngineeringValidationError(f"Ungültige RoutingRule-Priorität: {priority}.")
    if status not in ROUTE_STATUSES:
        raise EngineeringValidationError(f"Ungültiger RoutingRule-Status: {status}.")
    return {"name": name, "condition": condition, "action": action, "priority": priority, "status": status}


def create_rule(data: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_rule(data)
    with get_connection() as connection:
        row = connection.execute(
            "INSERT INTO engineering_routing_rules "
            "(name, condition, action, priority, status, created_by, modified_by) "
            "VALUES (%s, %s, %s, %s, 'DRAFT', %s, %s) RETURNING *",
            (
                normalized["name"], Jsonb(normalized["condition"]), Jsonb(normalized["action"]),
                normalized["priority"], data.get("actor"), data.get("actor"),
            ),
        ).fetchone()
        _audit(connection, None, "ROUTING_RULE_CREATED", actor=data.get("actor"), after=row)
        connection.commit()
    return row


def list_rules(*, status: str | None = None) -> list[dict[str, Any]]:
    values: list[Any] = []
    where = ""
    if status:
        where = " WHERE status = %s"
        values.append(status.upper())
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_routing_rules" + where + " ORDER BY modified_at DESC", values
        ).fetchall()


def get_rule(rule_id: str) -> dict[str, Any]:
    validate_uuid(rule_id)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM engineering_routing_rules WHERE id = %s", (rule_id,)
        ).fetchone()
    if row is None:
        raise NotFoundError(f"RoutingRule {rule_id} nicht gefunden.")
    return row


def update_rule(rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
    current = get_rule(rule_id)
    if current["status"] in ("APPROVED", "RELEASED"):
        raise EngineeringValidationError("Freigegebene RoutingRules sind unveränderlich.")
    normalized = _normalize_rule(data, current)
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_routing_rules SET name = %s, condition = %s, action = %s, "
            "priority = %s, status = %s, version = version + 1, modified_by = %s, "
            "modified_at = now() WHERE id = %s RETURNING *",
            (
                normalized["name"], Jsonb(normalized["condition"]), Jsonb(normalized["action"]),
                normalized["priority"], normalized["status"], data.get("actor"), rule_id,
            ),
        ).fetchone()
        _audit(connection, None, "ROUTING_RULE_EDITED", actor=data.get("actor"), before=current, after=row)
        connection.commit()
    return row


def delete_rule(rule_id: str, *, actor: str | None = None) -> None:
    current = get_rule(rule_id)
    if current["status"] in ("APPROVED", "RELEASED"):
        raise EngineeringValidationError("Freigegebene RoutingRules dürfen nicht gelöscht werden.")
    with get_connection() as connection:
        connection.execute("DELETE FROM engineering_routing_rules WHERE id = %s", (rule_id,))
        _audit(connection, None, "ROUTING_RULE_DELETED", actor=actor, before=current)
        connection.commit()


def record_simulation_results(
    route_ids: list[str], job_id: str, result: dict[str, Any]
) -> None:
    """Attach compact runtime observations to routes without copying signal definitions."""
    observation = {
        "status": result.get("status"),
        "events": (result.get("trace") or {}).get("events"),
        "technologies": (result.get("trace") or {}).get("technologies", []),
        "hardware_valid": (result.get("hardware_validation") or {}).get("valid"),
        "warnings": result.get("warnings", []),
    }
    with get_connection() as connection:
        for route_id in route_ids:
            validate_uuid(route_id)
            row = connection.execute(
                "SELECT id, route_code FROM engineering_routing_entries WHERE id = %s",
                (route_id,),
            ).fetchone()
            if row is None:
                continue
            connection.execute(
                "INSERT INTO engineering_relations "
                "(relation_type, source_type, source_id, target_type, target_id, attributes, source, "
                "provenance, review_state, approval_state, created_by) "
                "VALUES ('SIMULATED_IN', 'RoutingEntry', %s, 'SimulationRun', %s, %s, "
                "'simulation_derived', %s, 'reviewed', 'approved', 'simulation-service') "
                "ON CONFLICT (relation_type, source_type, source_id, target_type, target_id) "
                "DO UPDATE SET attributes = EXCLUDED.attributes",
                (
                    route_id,
                    job_id,
                    Jsonb({"job_id": job_id, "observation": observation}),
                    Jsonb({"origin": "communication-simulator"}),
                ),
            )
            _audit(
                connection,
                route_id,
                "ROUTE_USED_IN_SIMULATION",
                actor="simulation-service",
                after={"job_id": job_id, "observation": observation},
                evidence=[observation],
            )
        connection.commit()
