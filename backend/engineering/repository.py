"""Generische Persistenzschicht für die kanonischen Engineering-Objekte.

Alle Entitätstabellen (``engineering_hardware_nodes``, ``engineering_functions``,
``engineering_hardware_interfaces``, ``engineering_interfaces``,
``engineering_messages``, ``engineering_signals``)
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

from .db import get_connection, ConcurrentUpdateError, check_revision, mark_model_changed
from .project_context import current_project_id
from .models import (
    ADDRESS_ASSIGNMENT_MODES,
    ADDRESS_STATUSES,
    APPROVAL_STATES,
    CLASSIFICATION_STATUSES,
    DATA_COMPLEXITIES,
    DEVICE_TYPES,
    DEVICE_TYPINGS,
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
from .device_classification import DeviceClassificationRegistry
from .scope_rules import (
    communication_system_allows_interface,
    hardware_scope_category,
    normalize_engineering_scope_rules,
    scope_placeholder_sql,
)
from .structure_rules import (
    equivalent_system_names,
    infer_device_type,
    is_placeholder_system_name,
    normalize_hardware_name,
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
            "device_class",
            "device_typing",
            "data_complexity",
            "classification_status",
            "capability_profile_ref",
            "identity",
            "product_information",
            "hardware_information",
            "software_information",
            "diagnostic_addressable",
            "logical_node_address",
            "address_assignment_mode",
            "address_status",
            "address_namespace",
            "address_provenance",
        ),
        json_columns=frozenset(
            {"identity", "product_information", "hardware_information", "software_information", "address_provenance"}
        ),
        enum_fields={
            "device_type": DEVICE_TYPES,
            "device_typing": DEVICE_TYPINGS,
            "data_complexity": DATA_COMPLEXITIES,
            "classification_status": CLASSIFICATION_STATUSES,
            "address_assignment_mode": ADDRESS_ASSIGNMENT_MODES,
            "address_status": ADDRESS_STATUSES,
        },
    ),
    "Function": EntitySpec(
        table="engineering_functions",
        object_type="Function",
        own_columns=("hardware_node_id",),
        json_columns=frozenset(),
        required=("hardware_node_id",),
    ),
    "HardwareNetworkInterface": EntitySpec(
        table="engineering_hardware_interfaces",
        object_type="HardwareNetworkInterface",
        own_columns=(
            "hardware_node_id",
            "technology",
            "controller_ref",
            "physical_port_ref",
            "channel_index",
            "network_ref",
            "bitrate",
            "data_bitrate",
            "capabilities",
            "status",
            "message_refs",
            "static_load",
            "runtime_load",
            "target_load_limit",
            "warning_load_limit",
            "hard_load_limit",
        ),
        json_columns=frozenset({"capabilities", "message_refs"}),
        required=("hardware_node_id", "technology"),
        enum_fields={"technology": INTERFACE_TYPES},
    ),
    "Interface": EntitySpec(
        table="engineering_interfaces",
        object_type="Interface",
        own_columns=("hardware_node_id", "function_id", "interface_type", "configuration"),
        json_columns=frozenset({"configuration"}),
        required=("interface_type",),
        enum_fields={"interface_type": INTERFACE_TYPES},
    ),
    "Message": EntitySpec(
        table="engineering_messages",
        object_type="Message",
        own_columns=(
            "interface_id",
            "hardware_interface_id",
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
    "HardwareNetworkInterface": ("hardware_node_id", "HardwareNode", "HAS_HARDWARE_INTERFACE"),
    "Interface": ("function_id", "Function", "HAS_INTERFACE"),
    "Message": ("interface_id", "Interface", "HAS_MESSAGE"),
    "Signal": ("message_id", "Message", "CONTAINS_SIGNAL"),
}


def parent_link_for_payload(
    object_type: str,
    payload: dict[str, Any],
) -> tuple[str, str, str] | None:
    """Return the canonical parent relation for an object payload.

    Logical interfaces may belong either to a function or, for class 0-2
    devices, directly to the hardware node.
    """
    if object_type == "Interface":
        if payload.get("function_id"):
            return "function_id", "Function", "HAS_INTERFACE"
        if payload.get("hardware_node_id"):
            return "hardware_node_id", "HardwareNode", "HAS_INTERFACE"
        return None
    return PARENT_LINKS.get(object_type)


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


def _apply_hardware_classification_defaults(data: dict[str, Any]) -> dict[str, Any]:
    supplied = any(data.get(field) not in (None, "") for field in ("device_class", "device_typing", "data_complexity"))
    registry = DeviceClassificationRegistry()
    profile = registry.resolve_profile(
        name=str(data.get("name") or ""),
        device_type=str(data.get("device_type") or "GenericDevice"),
        device_class=data.get("device_class"),
        device_typing=str(data.get("device_typing") or "") or None,
        data_complexity=str(data.get("data_complexity") or "") or None,
    )
    payload = {
        **data,
        "device_class": profile.device_class,
        "device_typing": profile.device_typing,
        "data_complexity": profile.data_complexity,
        "classification_status": data.get("classification_status") or ("CONFIRMED" if supplied else "PROPOSED"),
        "capability_profile_ref": data.get("capability_profile_ref") or profile.capability_profile_ref,
    }
    hardware_information = dict(payload.get("hardware_information") or {})
    hardware_information["device_capability_profile"] = profile.to_dict()
    hardware_information["generator_policy"] = profile.generator_policy
    payload["hardware_information"] = hardware_information
    from .addressing import default_addressability_for_class, parse_logical_node_address
    address_provenance = dict(payload.get("address_provenance") or {})
    if "diagnostic_addressable" in data and data.get("diagnostic_addressable") is not None:
        payload["diagnostic_addressable"] = bool(data["diagnostic_addressable"])
        address_provenance["addressability_source"] = "explicit"
    else:
        payload["diagnostic_addressable"] = default_addressability_for_class(profile.device_class)
        address_provenance["addressability_source"] = "policy"
    payload["address_namespace"] = str(payload.get("address_namespace") or "PROJECT").upper()
    # A proposal may decide that a node is diagnostically addressable, but it
    # must never manufacture the identifier itself.  Imported data and manual
    # UI/API edits remain explicit; AI-created nodes always pass through the
    # single authoritative allocator after the INSERT.
    if str(payload.get("source") or "").lower() == "ai_generated":
        payload["logical_node_address"] = None
        payload["address_assignment_mode"] = "AUTO"
        address_provenance["ignored_ai_address"] = data.get("logical_node_address")
    if payload.get("logical_node_address") not in (None, ""):
        payload["logical_node_address"] = parse_logical_node_address(payload["logical_node_address"])
        payload["diagnostic_addressable"] = True
        address_provenance["addressability_source"] = (
            "import" if payload.get("source") == "import" else "explicit"
        )
        payload["address_assignment_mode"] = str(
            payload.get("address_assignment_mode") or ("IMPORTED" if payload.get("source") == "import" else "MANUAL")
        ).upper()
        payload["address_status"] = "ASSIGNED"
    else:
        payload["logical_node_address"] = None
        payload["address_assignment_mode"] = str(payload.get("address_assignment_mode") or "AUTO").upper()
        payload["address_status"] = "UNASSIGNED"
    payload["address_provenance"] = address_provenance
    return payload


def _enforce_engineering_scope_rules(
    connection,
    object_type: str,
    payload: dict[str, Any],
    project_id: str,
) -> None:
    if object_type not in {"HardwareNode", "Interface"}:
        return
    row = connection.execute(
        "SELECT context FROM engineering_workflow_projects WHERE project_id = %s FOR UPDATE",
        (project_id,),
    ).fetchone()
    raw_rules = (row.get("context") or {}).get("engineering_scope_rules") if row else None
    if not raw_rules:
        return
    rules = normalize_engineering_scope_rules(raw_rules)

    if object_type == "Interface":
        allowed = rules["communication_systems"]
        interface_type = str(payload.get("interface_type") or "")
        if not communication_system_allows_interface(allowed, interface_type):
            raise EngineeringValidationError(
                f"Interface-Typ {interface_type!r} ist durch die Projektregel nicht erlaubt. "
                f"Zulaessig: {', '.join(allowed)}."
            )
        return

    category = hardware_scope_category(payload.get("device_type"))
    if not category:
        return
    if category not in rules["hardware_counts"]:
        return
    limit = rules["hardware_counts"][category]
    current_row = connection.execute(
        "SELECT count(*) AS count FROM engineering_hardware_nodes h "
        f"WHERE project_id = %s AND device_type = %s AND NOT {scope_placeholder_sql('h')}",
        (project_id, payload.get("device_type")),
    ).fetchone()
    current_count = int(current_row["count"] if current_row else 0)
    if current_count >= limit:
        raise EngineeringValidationError(
            f"Projektregel verletzt: Fuer {category} gilt exakt {limit}; "
            f"bereits vorhanden sind {current_count}."
        )


def create_object(object_type: str, data: dict[str, Any]) -> dict[str, Any]:
    spec = get_spec(object_type)
    if not data.get("name"):
        raise EngineeringValidationError("Pflichtfeld fehlt: 'name'")
    if object_type == "Interface" and not (data.get("function_id") or data.get("hardware_node_id")):
        raise EngineeringValidationError("Pflichtfeld fehlt: 'function_id' oder 'hardware_node_id'")
    if object_type == "HardwareNode":
        data = {
            **data,
            "device_type": data.get("device_type") or infer_device_type(str(data["name"])),
            "name": normalize_hardware_name(data["name"]),
        }
        if is_placeholder_system_name(data["name"]):
            raise EngineeringValidationError(
                f"{data['name']!r} ist eine Objektart oder ein Platzhalter, aber kein technischer Systemname."
            )
        data = _apply_hardware_classification_defaults(data)
    if object_type == "Interface" and data.get("function_id"):
        parent_function = get_object("Function", str(data["function_id"]))
        data = {**data, "hardware_node_id": parent_function["hardware_node_id"]}
    spec.validate(data)

    columns = list(BASE_COLUMNS) + list(spec.own_columns)
    payload = {col: data[col] for col in columns if col in data}
    payload.update(_governance_defaults(data))
    project_id = current_project_id()
    if object_type == "HardwareNode" and payload.get("logical_node_address") is not None:
        from .addressing import LogicalNodeAddressAllocator
        validation = LogicalNodeAddressAllocator(project_id, str(payload.get("address_namespace") or "PROJECT")).validate_address(
            payload["logical_node_address"]
        )
        if not validation["valid"]:
            raise EngineeringValidationError(validation["errors"][0]["message"])
    parent_link = parent_link_for_payload(object_type, payload)
    if parent_link and payload.get(parent_link[0]):
        get_object(parent_link[1], str(payload[parent_link[0]]))
    if object_type == "Interface" and not payload.get("function_id") and payload.get("hardware_node_id"):
        get_object("HardwareNode", str(payload["hardware_node_id"]))
    if object_type == "Message" and payload.get("hardware_interface_id"):
        get_object("HardwareNetworkInterface", str(payload["hardware_interface_id"]))

    insert_columns = ["project_id", *payload.keys()]
    values = [project_id, *[_wrap_value(col, payload[col], spec) for col in payload]]

    query = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *"
    ).format(
        table=sql.Identifier(spec.table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in insert_columns),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(insert_columns)),
    )

    with get_connection() as conn:
        _enforce_engineering_scope_rules(conn, object_type, payload, project_id)
        row = conn.execute(query, values).fetchone()
        if object_type == "HardwareNode":
            from .addressing import LogicalNodeAddressAllocator
            allocator = LogicalNodeAddressAllocator(project_id, str(row.get("address_namespace") or "PROJECT"))
            if row.get("logical_node_address") is None:
                row = allocator.assign_address(
                    str(row["id"]), assignment_mode="AUTO", actor=payload.get("created_by"), connection=conn,
                )
            elif row.get("diagnostic_addressable"):
                allocator._audit(conn, str(row["id"]), "ADDRESS_ASSIGNED", payload.get("created_by"), None, row)
        row = _decorate_row(spec, row)
        _write_version_snapshot(conn, spec, row, changed_by=payload.get("created_by"), summary="created")
        if parent_link:
            parent_field, parent_type, relation_type = parent_link
            conn.execute(
                "INSERT INTO engineering_relations "
                "(project_id, relation_type, source_type, source_id, target_type, target_id, "
                "source, provenance, review_state, approval_state, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    project_id,
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
    mark_model_changed()
    return row


def get_object(object_type: str, object_id: str) -> dict[str, Any]:
    spec = get_spec(object_type)
    _validate_uuid(object_id)
    query = sql.SQL("SELECT * FROM {table} WHERE id = %s AND project_id = %s").format(table=sql.Identifier(spec.table))
    with get_connection() as conn:
        row = conn.execute(query, (object_id, current_project_id())).fetchone()
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
    where_clauses: list[sql.Composable] = [sql.SQL("project_id = %s")]
    values: list[Any] = [current_project_id()]
    placeholder = scope_placeholder_sql("h")
    if object_type == "HardwareNode":
        where_clauses.append(sql.SQL(f"NOT {scope_placeholder_sql('engineering_hardware_nodes')}"))
    elif object_type in {"Function", "Interface"}:
        where_clauses.append(
            sql.SQL(
                "hardware_node_id NOT IN (SELECT h.id FROM engineering_hardware_nodes h "
                f"WHERE h.project_id = %s AND {placeholder})"
            )
        )
        values.append(current_project_id())
    elif object_type == "Message":
        where_clauses.append(
            sql.SQL(
                "interface_id NOT IN (SELECT i.id FROM engineering_interfaces i "
                "JOIN engineering_hardware_nodes h ON h.id = i.hardware_node_id AND h.project_id = i.project_id "
                f"WHERE h.project_id = %s AND {placeholder})"
            )
        )
        values.append(current_project_id())
    elif object_type == "Signal":
        where_clauses.append(
            sql.SQL(
                "message_id NOT IN (SELECT m.id FROM engineering_messages m "
                "JOIN engineering_interfaces i ON i.id = m.interface_id AND i.project_id = m.project_id "
                "JOIN engineering_hardware_nodes h ON h.id = i.hardware_node_id AND h.project_id = i.project_id "
                f"WHERE h.project_id = %s AND {placeholder})"
            )
        )
        values.append(current_project_id())
    for column, value in filters.items():
        if column not in allowed_filter_columns or value is None:
            continue
        where_clauses.append(sql.SQL("{col} = %s").format(col=sql.Identifier(column)))
        values.append(value)

    where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_clauses)
    query = sql.SQL(
        "SELECT * FROM {table}{where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    ).format(table=sql.Identifier(spec.table), where=where_sql)
    values.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, values).fetchall()
    return [_decorate_row(spec, row) for row in rows]


def find_equivalent_hardware_node(data: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a proposed HardwareNode to an existing canonical system.

    This intentionally uses controlled system-name aliases and compatible metadata,
    not a broad fuzzy-name match. It therefore recognizes ADAS/Fahrerassistenz while
    keeping unrelated systems such as Abgasnachbehandlung and Airbag separate.
    """

    proposed_name = str(data.get("name") or "").strip()
    if not proposed_name:
        return None
    proposed_domain = str(data.get("domain") or "").strip().casefold()
    proposed_device_type = str(
        data.get("device_type") or infer_device_type(proposed_name)
    ).strip()
    generic_types = {"", "GenericDevice", "CustomDevice"}
    matches: list[tuple[tuple[int, float, int, int, str], dict[str, Any]]] = []
    for candidate in list_objects("HardwareNode", limit=5000):
        candidate_domain = str(candidate.get("domain") or "").strip().casefold()
        equivalent, similarity = equivalent_system_names(
            proposed_name,
            candidate.get("name"),
            domain=proposed_domain if proposed_domain and proposed_domain == candidate_domain else None,
        )
        if not equivalent:
            continue
        if proposed_domain and candidate_domain and proposed_domain != candidate_domain:
            continue
        candidate_device_type = str(candidate.get("device_type") or "").strip()
        if (
            proposed_device_type not in generic_types
            and candidate_device_type not in generic_types
            and proposed_device_type != candidate_device_type
        ):
            continue
        reason = (
            "gleichnamiges kanonisches System"
            if proposed_name.casefold() == str(candidate.get("name") or "").strip().casefold()
            else "kontrolliertes Fachsynonym"
        )
        resolution = {
            "hardware": candidate,
            "similarity": similarity,
            "reason": reason,
        }
        function_count = len(
            list_objects(
                "Function",
                filters={"hardware_node_id": str(candidate.get("id") or "")},
                limit=5000,
            )
        )
        resolution["child_count"] = function_count
        rank = (
            function_count,
            similarity,
            int(candidate.get("approval_state") == "approved"),
            int(candidate.get("review_state") == "reviewed"),
            str(candidate.get("name") or "").casefold(),
        )
        matches.append((rank, resolution))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def update_object(object_type: str, object_id: str, data: dict[str, Any]) -> dict[str, Any]:
    spec = get_spec(object_type)
    _validate_uuid(object_id)
    existing = get_object(object_type, object_id)
    check_revision(data.get("expected_version"), existing["version"])

    editable_columns = list(BASE_COLUMNS) + list(spec.own_columns) + [
        "source",
        "provenance",
        "confidence",
        "review_state",
        "approval_state",
        "lifecycle_state",
    ]
    updates = {col: data[col] for col in editable_columns if col in data}
    if object_type == "HardwareNode":
        if str(data.get("source") or "").lower() == "ai_generated":
            for field in ("logical_node_address", "address_assignment_mode", "address_namespace"):
                updates.pop(field, None)
        requested_name = str(updates.get("name", existing.get("name") or ""))
        if "name" in updates and "device_type" not in updates:
            updates["device_type"] = infer_device_type(
                requested_name,
                str(existing.get("device_type") or "GenericDevice"),
            )
        if "name" in updates or "device_type" in updates:
            updates["name"] = normalize_hardware_name(requested_name)
        if any(field in updates for field in ("name", "device_type", "device_class", "device_typing", "data_complexity")):
            merged = _apply_hardware_classification_defaults({**existing, **updates})
            for field in ("device_class", "device_typing", "data_complexity", "classification_status", "capability_profile_ref", "hardware_information"):
                updates[field] = merged[field]
        address_fields = {"diagnostic_addressable", "logical_node_address", "address_assignment_mode", "address_namespace"}
        if address_fields & updates.keys():
            from .addressing import LogicalNodeAddressAllocator, parse_logical_node_address
            requested_address = updates.get("logical_node_address", existing.get("logical_node_address"))
            requested_address = (
                parse_logical_node_address(requested_address) if requested_address not in (None, "") else None
            )
            address_will_change = (
                requested_address != existing.get("logical_node_address")
                or bool(updates.get("diagnostic_addressable", existing.get("diagnostic_addressable")))
                != bool(existing.get("diagnostic_addressable"))
            )
            if address_will_change and not bool(data.get("confirm_address_change")):
                raise EngineeringValidationError(
                    "Adressänderung erfordert confirm_address_change=true; zuvor die Impact-Analyse aufrufen."
                )
            addressable = bool(updates.get("diagnostic_addressable", existing.get("diagnostic_addressable")))
            address_provenance = dict(existing.get("address_provenance") or {})
            address_provenance.update({"addressability_source": "explicit", "actor": data.get("actor") or data.get("modified_by")})
            updates["diagnostic_addressable"] = addressable
            updates["address_namespace"] = str(updates.get("address_namespace") or existing.get("address_namespace") or "PROJECT").upper()
            if not addressable or updates.get("logical_node_address", existing.get("logical_node_address")) in (None, ""):
                updates["logical_node_address"] = None
                updates["address_status"] = "UNASSIGNED"
            else:
                parsed = requested_address
                validation = LogicalNodeAddressAllocator(current_project_id(), updates["address_namespace"]).validate_address(parsed, node_id=object_id)
                if not validation["valid"]:
                    raise EngineeringValidationError(validation["errors"][0]["message"])
                updates["logical_node_address"] = parsed
                updates["address_assignment_mode"] = str(updates.get("address_assignment_mode") or "MANUAL").upper()
                updates["address_status"] = "ASSIGNED"
            updates["address_provenance"] = address_provenance
    parent_link = parent_link_for_payload(object_type, {**existing, **updates})
    parent = None
    if object_type == "Interface" and ("function_id" in updates or "hardware_node_id" in updates):
        next_function_id = updates.get("function_id", existing.get("function_id"))
        next_hardware_node_id = updates.get("hardware_node_id", existing.get("hardware_node_id"))
        if not (next_function_id or next_hardware_node_id):
            raise EngineeringValidationError("Pflichtfeld fehlt: 'function_id' oder 'hardware_node_id'")
        if not next_function_id and next_hardware_node_id:
            get_object("HardwareNode", str(next_hardware_node_id))
    if parent_link and parent_link[0] in updates:
        parent_field, parent_type, _ = parent_link
        if not updates.get(parent_field):
            raise EngineeringValidationError(f"Pflichtfeld fehlt: {parent_field!r}")
        parent = get_object(parent_type, str(updates[parent_field]))
        if object_type == "Interface" and parent.get("hardware_node_id"):
            updates["hardware_node_id"] = parent["hardware_node_id"]
    if object_type == "Message" and updates.get("hardware_interface_id"):
        get_object("HardwareNetworkInterface", str(updates["hardware_interface_id"]))
    if not updates:
        return existing

    spec.validate({**existing, **updates})

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

    effective_updates = {
        key: value
        for key, value in updates.items()
        if not (
            existing.get(key) == value
            or (
                isinstance(existing.get(key), uuid.UUID)
                and value is not None
                and str(existing[key]) == str(value)
            )
        )
    }
    if not effective_updates:
        return existing
    updates = effective_updates

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
        "UPDATE {table} SET {set_sql}, modified_at = now() WHERE id = %s AND project_id = %s AND version = %s RETURNING *"
    ).format(table=sql.Identifier(spec.table), set_sql=set_sql)

    with get_connection() as conn:
        row = conn.execute(query, [*values, object_id, current_project_id(), existing["version"]]).fetchone()
        if row is None:
            raise ConcurrentUpdateError("Objekt wurde parallel geändert. Bitte neu laden.")
        row = _decorate_row(spec, row)
        if object_type == "HardwareNode" and (
            existing.get("logical_node_address") != row.get("logical_node_address")
            or existing.get("diagnostic_addressable") != row.get("diagnostic_addressable")
        ):
            from .addressing import LogicalNodeAddressAllocator
            allocator = LogicalNodeAddressAllocator(current_project_id(), str(row.get("address_namespace") or "PROJECT"))
            event = "ADDRESS_RELEASED" if row.get("logical_node_address") is None else "ADDRESS_CHANGED"
            allocator._audit(conn, object_id, event, actor, existing, row)
            allocator._mark_dependents_outdated(conn, object_id, existing, row, actor)
        if parent_link and parent_link[0] in updates:
            parent_field, parent_type, relation_type = parent_link
            project_id = current_project_id()
            conn.execute(
                "DELETE FROM engineering_relations "
                "WHERE project_id = %s AND relation_type = %s "
                "AND target_type = %s AND target_id = %s",
                (project_id, relation_type, object_type, object_id),
            )
            parent_changed = str(existing.get(parent_field) or "") != str(updates[parent_field])
            relation_source = data.get("relation_source") or (
                "manual" if parent_changed else existing.get("source") or "manual"
            )
            validate_choice(str(relation_source), SOURCES, "relation_source")
            conn.execute(
                "INSERT INTO engineering_relations "
                "(project_id, relation_type, source_type, source_id, target_type, target_id, "
                "attributes, source, provenance, confidence, review_state, approval_state, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    project_id,
                    relation_type,
                    parent_type,
                    updates[parent_field],
                    object_type,
                    object_id,
                    Jsonb(data.get("relation_attributes", {})),
                    relation_source,
                    Jsonb(data.get("relation_provenance", {})),
                    data.get("relation_confidence"),
                    data.get("relation_review_state", "reviewed"),
                    data.get("relation_approval_state", "approved"),
                    actor,
                ),
            )
        _write_version_snapshot(
            conn, spec, row, changed_by=actor, summary=data.get("change_summary", "updated")
        )
    mark_model_changed()
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
    project_id = current_project_id()
    query = sql.SQL("DELETE FROM {table} WHERE id = %s AND project_id = %s").format(table=sql.Identifier(spec.table))
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM engineering_relations "
            "WHERE project_id = %s AND ((source_type = %s AND source_id = %s) "
            "OR (target_type = %s AND target_id = %s))",
            (project_id, object_type, object_id, object_type, object_id),
        )
        conn.execute(query, (object_id, project_id))
        conn.execute(
            "DELETE FROM engineering_object_versions WHERE project_id = %s AND object_type = %s AND object_id = %s",
            (project_id, object_type, object_id),
        )

    mark_model_changed()


def list_versions(object_type: str, object_id: str) -> list[dict[str, Any]]:
    get_spec(object_type)
    _validate_uuid(object_id)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM engineering_object_versions "
            "WHERE project_id = %s AND object_type = %s AND object_id = %s ORDER BY version DESC",
            (current_project_id(), object_type, object_id),
        ).fetchall()
    return rows


def _write_version_snapshot(conn, spec: EntitySpec, row: dict[str, Any], *, changed_by, summary) -> None:
    conn.execute(
        "INSERT INTO engineering_object_versions "
        "(project_id, object_type, object_id, version, snapshot, change_summary, changed_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            current_project_id(),
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
    decorated = {**row, "object_type": spec.object_type}
    if spec.object_type == "HardwareNode":
        from .addressing import LogicalNodeAddress, format_logical_node_address
        value = decorated.get("logical_node_address")
        decorated["formatted_logical_node_address"] = format_logical_node_address(int(value)) if value is not None else None
        decorated["logical_node_address_object"] = (
            LogicalNodeAddress(
                int(value), decorated.get("address_namespace") or "PROJECT",
                decorated.get("address_assignment_mode") or "AUTO", decorated.get("address_status") or "ASSIGNED",
                dict(decorated.get("address_provenance") or {}),
            ).to_dict() if value is not None else None
        )
    return decorated
