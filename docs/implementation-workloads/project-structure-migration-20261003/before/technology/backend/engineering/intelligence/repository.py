"""Persistence for governed optimization proposals."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from ..db import get_connection
from ..models import EngineeringValidationError
from ..repository import NotFoundError

PROPOSAL_STATUSES = (
    "PROPOSED",
    "UNDER_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "APPLIED_AS_DRAFT",
    "SUPERSEDED",
)


def create_optimization_proposal(project_id: str, data: dict[str, Any]) -> dict[str, Any]:
    required = ("category", "problem", "recommendation")
    missing = [field for field in required if not str(data.get(field) or "").strip()]
    if missing:
        raise EngineeringValidationError(f"Pflichtfelder fehlen: {', '.join(missing)}")
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO engineering_optimization_proposals
                (project_id, source_snapshot_id, category, problem, affected_objects,
                 recommendation, expected_impact, evidence, graph_context, rag_context,
                 confidence, priority, implementation_effort, provenance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                project_id,
                data.get("source_snapshot_id"),
                str(data["category"]),
                str(data["problem"]),
                Jsonb(data.get("affected_objects") or []),
                str(data["recommendation"]),
                Jsonb(data.get("expected_impact") or {}),
                Jsonb(data.get("evidence") or []),
                Jsonb(data.get("graph_context") or []),
                Jsonb(data.get("rag_context") or []),
                data.get("confidence"),
                max(0, min(100, int(data.get("priority") or 50))),
                str(data.get("implementation_effort") or "MEDIUM").upper(),
                Jsonb(data.get("provenance") or {}),
            ),
        ).fetchone()
    return row


def list_optimization_proposals(
    project_id: str, *, status: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    query = "SELECT * FROM engineering_optimization_proposals WHERE project_id = %s"
    values: list[Any] = [project_id]
    if status:
        normalized = status.upper()
        if normalized not in PROPOSAL_STATUSES:
            raise EngineeringValidationError("Unbekannter Proposal-Status.")
        query += " AND status = %s"
        values.append(normalized)
    query += " ORDER BY priority DESC, created_at DESC LIMIT %s"
    values.append(min(max(int(limit), 1), 500))
    with get_connection() as connection:
        return connection.execute(query, values).fetchall()


def update_optimization_proposal(
    project_id: str, proposal_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    status = str(data.get("status") or "").upper()
    if status not in PROPOSAL_STATUSES:
        raise EngineeringValidationError("Unbekannter Proposal-Status.")
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE engineering_optimization_proposals
            SET status = %s, reviewed_by = %s, review_reason = %s, updated_at = now()
            WHERE proposal_id = %s AND project_id = %s
            RETURNING *
            """,
            (status, data.get("actor"), data.get("reason"), proposal_id, project_id),
        ).fetchone()
    if row is None:
        raise NotFoundError(f"OptimizationProposal {proposal_id} nicht gefunden.")
    return row
