"""Persistenz für Relations (Kanten) zwischen Engineering-Objekten.

Dies ist die minimale Grundlage für den in Abschnitt 7 der Spezifikation
beschriebenen Engineering Knowledge Graph. Eine dedizierte Graph-Datenbank
wird hier bewusst noch nicht eingeführt (siehe Entwicklungsreihenfolge:
zunächst das kanonische Modell, Graph-/RAG-Layer folgen in späteren Phasen);
``engineering_relations`` speichert Kanten aber bereits so, dass sie später
1:1 in einen Graph-Store übernommen werden können.
"""

from __future__ import annotations

import uuid
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from .db import get_connection
from .models import (
    APPROVAL_STATES,
    EngineeringValidationError,
    RELATABLE_OBJECT_TYPES,
    RELATION_TYPES,
    REVIEW_STATES,
    SOURCES,
    validate_choice,
    validate_uuid as _validate_uuid,
)
from .repository import NotFoundError, get_object


def create_relation(data: dict[str, Any]) -> dict[str, Any]:
    required = ("relation_type", "source_type", "source_id", "target_type", "target_id")
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise EngineeringValidationError(f"Pflichtfelder fehlen: {', '.join(missing)}")

    validate_choice(data["relation_type"], RELATION_TYPES, "relation_type")
    validate_choice(data["source_type"], RELATABLE_OBJECT_TYPES, "source_type")
    validate_choice(data["target_type"], RELATABLE_OBJECT_TYPES, "target_type")
    _validate_uuid(data["source_id"])
    _validate_uuid(data["target_id"])

    # Referenzielle Konsistenz: beide Endpunkte müssen existieren.
    get_object(data["source_type"], data["source_id"])
    get_object(data["target_type"], data["target_id"])

    source = data.get("source", "manual")
    validate_choice(source, SOURCES, "source")
    review_state = data.get("review_state", "unreviewed")
    validate_choice(review_state, REVIEW_STATES, "review_state")
    approval_state = data.get("approval_state", "pending")
    validate_choice(approval_state, APPROVAL_STATES, "approval_state")

    with get_connection() as conn:
        row = conn.execute(
            "INSERT INTO engineering_relations "
            "(relation_type, source_type, source_id, target_type, target_id, "
            "attributes, source, provenance, confidence, review_state, "
            "approval_state, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                data["relation_type"],
                data["source_type"],
                data["source_id"],
                data["target_type"],
                data["target_id"],
                Jsonb(data.get("attributes", {})),
                source,
                Jsonb(data.get("provenance", {})),
                data.get("confidence"),
                review_state,
                approval_state,
                data.get("created_by") or data.get("actor"),
            ),
        ).fetchone()
        conn.commit()
    return row


def get_relation(relation_id: str) -> dict[str, Any]:
    _validate_uuid(relation_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM engineering_relations WHERE id = %s", (relation_id,)
        ).fetchone()
    if row is None:
        raise NotFoundError(f"Relation {relation_id} nicht gefunden.")
    return row


def list_relations(
    *,
    object_type: str | None = None,
    object_id: str | None = None,
    relation_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[sql.Composable] = []
    values: list[Any] = []

    if object_type and object_id:
        _validate_uuid(object_id)
        clauses.append(
            sql.SQL(
                "((source_type = %s AND source_id = %s) OR (target_type = %s AND target_id = %s))"
            )
        )
        values.extend([object_type, object_id, object_type, object_id])
    if relation_type:
        clauses.append(sql.SQL("relation_type = %s"))
        values.append(relation_type)

    where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("")
    query = sql.SQL(
        "SELECT * FROM engineering_relations{where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    ).format(where=where_sql)
    values.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, values).fetchall()
    return rows


def delete_relation(relation_id: str) -> None:
    get_relation(relation_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM engineering_relations WHERE id = %s", (relation_id,))
        conn.commit()
