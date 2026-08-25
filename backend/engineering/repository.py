"""Generische Persistenzschicht für die kanonischen Engineering-Objekte.

Alle Entitätstabellen (``engineering_hardware_nodes``, ``engineering_functions``,
``engineering_interfaces``, ``engineering_messages``, ``engineering_signals``)
teilen sich dieselben Governance-Spalten (``version``, ``lifecycle_state``,
``source``, ``provenance``, ``confidence``, ``review_state``,
``approval_state``, ``created_at``/``created_by``, ``modified_at``/``modified_by``).
Diese generische Schicht kapselt CRUD- und Versionierungs-Logik einmalig,
statt sie für jede Entität zu duplizieren.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from .db import get_connection
from .models import (
    APPROVAL_STATES,
    DEVICE_TYPES,
    EngineeringValidationError,
    INTERFACE_TYPES,
    LIFECYCLE_STATES,
    MESSAGE_DIRECTIONS,
    REVIEW_STATES,
    SIGNAL_BYTE_ORDERS,
    SOURCES,
    validate_choice,
    validate_uuid as _validate_uuid,
)

GOVERNANCE_COLUMNS = (
    "version",
    "lifecycle_state",
    "source",
    "provenance",
    "confidence",
    "review_state",
    "approval_state",
    "created_at",
    "created_by",
    "modified_at",
    "modified_by",
)


class NotFoundError(LookupError):
    """Wird ausgelöst, wenn ein Engineering-Objekt nicht existiert."""


@dataclass(frozen=True)
class EntitySpec:
    """Beschreibt, wie eine Engineering-Entität persistiert wird."""

    table: str
    object_type: str
    # Spalten, die zusätzlich zu den Basis-/Governance-Feldern existieren.
    own_columns: tuple[str, ...]
    # Teilmenge von own_columns, die als JSONB gespeichert werden.
    json_columns: frozenset[str]
    # Pflichtfelder beim Anlegen (neben "name").
    required: tuple[str, ...] = ()
    # Feld -> erlaubte Werte, für einfache Enum-Validierung.
    enum_fields: dict[str, tuple[str, ...]] | None = None

    def validate(self, data: dict[str, Any]) -> None:
        for field_name, allowed in (self.enum_fields or {}).items():
            if field_name in data and data[field_name] is not None:
                validate_choice(data[field_name], allowed, field_name)
        for field_name in self.required:
            if not data.get(field_name):
                raise EngineeringValidationError(f"Pflichtfeld fehlt: {field_name!r}")


BASE_COLUMNS = ("name", "description", "domain")

ENTITY_SPECS: dict[str, EntitySpec] = {
    "HardwareNode": EntitySpec(
        table="engineering_hardware_nodes",
        object_type="HardwareNode",
        own_columns=(
            "device_type",
            "identity",
            "product_information",
            "hardware_information",
            "software_information",
        ),
        json_columns=frozenset(
            {"identity", "product_information", "hardware_information", "software_information"}
        ),
        enum_fields={"device_type": DEVICE_TYPES},
    ),
    "Function": EntitySpec(
        table="engineering_functions",
        object_type="Function",
        own_columns=("hardware_node_id",),
        json_columns=frozenset(),
        required=("hardware_node_id",),
    ),
    "Interface": EntitySpec(
        table="engineering_interfaces",
        object_type="Interface",
        own_columns=("hardware_node_id", "function_id", "interface_type", "configuration"),
        json_columns=frozenset({"configuration"}),
        required=("function_id", "interface_type"),
        enum_fields={"interface_type": INTERFACE_TYPES},
    ),
    "Message": EntitySpec(
        table="engineering_messages",
        object_type="Message",
        own_columns=(
            "interface_id",
            "message_id_hex",
            "direction",
            "cycle_ms",
            "dlc",
            "configuration",
        ),
        json_columns=frozenset({"configuration"}),
        required=("interface_id",),
        enum_fields={"direction": MESSAGE_DIRECTIONS},
    ),
    "Signal": EntitySpec(
        table="engineering_signals",
        object_type="Signal",
        own_columns=(
            "message_id",
            "display_name",
            "start_bit",
            "length_bits",
            "byte_order",
            "data_type",
            "factor",
            "offset_value",
            "unit",
            "min_value",
            "max_value",
            "configuration",
            "semantic",
            "data",
            "communication",
            "quality",
            "protocol_bindings",
        ),
        json_columns=frozenset(
            {"configuration", "semantic", "data", "communication", "quality", "protocol_bindings"}
        ),
        required=("message_id",),
        enum_fields={"byte_order": SIGNAL_BYTE_ORDERS},
    ),
}

PARENT_LINKS: dict[str, tuple[str, str, str]] = {
    "Function": ("hardware_node_id", "HardwareNode", "HAS_FUNCTION"),
    "Interface": ("function_id", "Function", "HAS_INTERFACE"),
    "Message": ("interface_id", "Interface", "HAS_MESSAGE"),
    "Signal": ("message_id", "Message", "CONTAINS_SIGNAL"),
}


def _all_columns(spec: EntitySpec) -> tuple[str, ...]:
    return BASE_COLUMNS + spec.own_columns + (
        "source",
        "provenance",
        "confidence",
        "review_state",
        "approval_state",
        "created_by",
    )


def _wrap_value(column: str, value: Any, spec: EntitySpec) -> Any:
    if column in spec.json_columns or column == "provenance":
        return Jsonb(value if value is not None else {})
    return value


def get_spec(object_type: str) -> EntitySpec:
    spec = ENTITY_SPECS.get(object_type)
    if spec is None:
        raise EngineeringValidationError(
            f"Unbekannter Objekttyp: {object_type!r}. "
            f"Erlaubt: {', '.join(ENTITY_SPECS)}."
        )
    return spec


def _governance_defaults(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source", "manual")
    validate_choice(source, SOURCES, "source")
    review_state = data.get("review_state", "unreviewed")
    validate_choice(review_state, REVIEW_STATES, "review_state")
    approval_state = data.get("approval_state", "pending")
    validate_choice(approval_state, APPROVAL_STATES, "approval_state")
    confidence = data.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise EngineeringValidationError("confidence muss zwischen 0 und 1 liegen.")
    return {
        "source": source,
        "provenance": data.get("provenance", {}),
        "confidence": confidence,
        "review_state": review_state,
        "approval_state": approval_state,
        "created_by": data.get("created_by") or data.get("actor"),
    }


def create_object(object_type: str, data: dict[str, Any]) -> dict[str, Any]:
    spec = get_spec(object_type)
    if not data.get("name"):
        raise EngineeringValidationError("Pflichtfeld fehlt: 'name'")
    spec.validate(data)

    columns = list(BASE_COLUMNS) + list(spec.own_columns)
    payload = {col: data.get(col) for col in columns}
    payload.update(_governance_defaults(data))

    insert_columns = list(payload.keys())
    values = [_wrap_value(col, payload[col], spec) for col in insert_columns]

    query = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *"
    ).format(
        table=sql.Identifier(spec.table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in insert_columns),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(insert_columns)),
    )

    with get_connection() as conn:
        row = conn.execute(query, values).fetchone()
        row = _decorate_row(spec, row)
        _write_version_snapshot(conn, spec, row, changed_by=payload.get("created_by"), summary="created")
        parent_link = PARENT_LINKS.get(object_type)
        if parent_link:
            parent_field, parent_type, relation_type = parent_link
            conn.execute(
                "INSERT INTO engineering_relations "
                "(relation_type, source_type, source_id, target_type, target_id, "
                "source, provenance, review_state, approval_state, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    relation_type,
                    parent_type,
                    payload[parent_field],
                    object_type,
                    row["id"],
                    payload["source"],
                    Jsonb(payload["provenance"]),
                    payload["review_state"],
                    payload["approval_state"],
                    payload.get("created_by"),
                ),
            )
        conn.commit()
    return row


def get_object(object_type: str, object_id: str) -> dict[str, Any]:
    spec = get_spec(object_type)
    _validate_uuid(object_id)
    query = sql.SQL("SELECT * FROM {table} WHERE id = %s").format(table=sql.Identifier(spec.table))
    with get_connection() as conn:
        row = conn.execute(query, (object_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"{object_type} {object_id} nicht gefunden.")
    return _decorate_row(spec, row)


def list_objects(
    object_type: str,
    *,
    filters: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    spec = get_spec(object_type)
    filters = filters or {}
    allowed_filter_columns = set(_all_columns(spec)) | {"id", "lifecycle_state", "review_state", "approval_state"}
    where_clauses: list[sql.Composable] = []
    values: list[Any] = []
    for column, value in filters.items():
        if column not in allowed_filter_columns or value is None:
            continue
        where_clauses.append(sql.SQL("{col} = %s").format(col=sql.Identifier(column)))
        values.append(value)

    where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses) if where_clauses else sql.SQL("")
    query = sql.SQL(
        "SELECT * FROM {table}{where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    ).format(table=sql.Identifier(spec.table), where=where_sql)
    values.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, values).fetchall()
    return [_decorate_row(spec, row) for row in rows]


def update_object(object_type: str, object_id: str, data: dict[str, Any]) -> dict[str, Any]:
    spec = get_spec(object_type)
    _validate_uuid(object_id)
    existing = get_object(object_type, object_id)

    editable_columns = list(BASE_COLUMNS) + list(spec.own_columns) + [
        "source",
        "provenance",
        "confidence",
        "review_state",
        "approval_state",
        "lifecycle_state",
    ]
    updates = {col: data[col] for col in editable_columns if col in data}
    if not updates:
        return existing

    for field_name, allowed in {
        "lifecycle_state": LIFECYCLE_STATES,
        "source": SOURCES,
        "review_state": REVIEW_STATES,
        "approval_state": APPROVAL_STATES,
        **(spec.enum_fields or {}),
    }.items():
        if field_name in updates and updates[field_name] is not None:
            validate_choice(updates[field_name], allowed, field_name)
    confidence = updates.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise EngineeringValidationError("confidence muss zwischen 0 und 1 liegen.")

    actor = data.get("modified_by") or data.get("actor")
    set_columns = list(updates.keys()) + ["version", "modified_by"]
    set_sql = sql.SQL(", ").join(
        sql.SQL("{col} = %s").format(col=sql.Identifier(c)) for c in set_columns
    )
    values = [_wrap_value(col, updates[col], spec) for col in updates] + [
        existing["version"] + 1,
        actor,
    ]

    query = sql.SQL(
        "UPDATE {table} SET {set_sql}, modified_at = now() WHERE id = %s RETURNING *"
    ).format(table=sql.Identifier(spec.table), set_sql=set_sql)

    with get_connection() as conn:
        row = conn.execute(query, [*values, object_id]).fetchone()
        row = _decorate_row(spec, row)
        _write_version_snapshot(
            conn, spec, row, changed_by=actor, summary=data.get("change_summary", "updated")
        )
        conn.commit()
    return row


def delete_object(object_type: str, object_id: str) -> None:
    """Löscht ein Objekt. Nur im Status ``draft`` erlaubt, um versionierte /

    bereits freigegebene Engineering-Objekte vor versehentlichem Verlust zu
    schützen.
    """
    spec = get_spec(object_type)
    existing = get_object(object_type, object_id)
    if existing["lifecycle_state"] != "draft":
        raise EngineeringValidationError(
            "Nur Objekte im Status 'draft' können gelöscht werden. "
            "Setze den lifecycle_state auf 'deprecated', um ein freigegebenes "
            "Objekt stattdessen auszumustern."
        )
    query = sql.SQL("DELETE FROM {table} WHERE id = %s").format(table=sql.Identifier(spec.table))
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM engineering_relations "
            "WHERE (source_type = %s AND source_id = %s) "
            "OR (target_type = %s AND target_id = %s)",
            (object_type, object_id, object_type, object_id),
        )
        conn.execute(query, (object_id,))
        conn.execute(
            "DELETE FROM engineering_object_versions WHERE object_type = %s AND object_id = %s",
            (object_type, object_id),
        )
        conn.commit()


def list_versions(object_type: str, object_id: str) -> list[dict[str, Any]]:
    get_spec(object_type)
    _validate_uuid(object_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM engineering_object_versions "
            "WHERE object_type = %s AND object_id = %s ORDER BY version DESC",
            (object_type, object_id),
        ).fetchall()
    return rows


def _write_version_snapshot(conn, spec: EntitySpec, row: dict[str, Any], *, changed_by, summary) -> None:
    conn.execute(
        "INSERT INTO engineering_object_versions "
        "(object_type, object_id, version, snapshot, change_summary, changed_by) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            spec.object_type,
            row["id"],
            row["version"],
            Jsonb(_json_safe(row)),
            summary,
            changed_by,
        ),
    )


def _json_safe(row: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            safe[key] = str(value)
        elif hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    return safe


def _decorate_row(spec: EntitySpec, row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "object_type": spec.object_type}
