"""Domain vocabularies and normalization for technology-neutral routing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..models import EngineeringValidationError

ROUTING_TYPES = (
    "UNICAST",
    "MULTICAST",
    "BROADCAST",
    "PUBLISH_SUBSCRIBE",
    "REQUEST_RESPONSE",
    "CYCLIC",
    "EVENT_BASED",
    "CONDITIONAL",
    "REDUNDANT",
    "GATEWAY_ROUTED",
)

ROUTE_STATUSES = (
    "DRAFT",
    "PENDING_CONFIRMATION",
    "READY_FOR_REVIEW",
    "APPROVED",
    "RELEASED",
    "REJECTED",
    "CONFLICT",
    "SUPERSEDED",
    "DEPRECATED",
    "OUTDATED",
)

ROUTING_ORIGINS = (
    "MANUAL",
    "IMPORTED",
    "AI_GENERATED",
    "AI_MODIFIED",
    "DERIVED",
    "NETWORK_EDITOR",
)
ROUTING_REVIEW_STATES = ("UNREVIEWED", "IN_REVIEW", "REVIEWED", "REJECTED")
ROUTING_APPROVAL_STATES = ("PENDING", "APPROVED", "REJECTED")
PROPOSAL_STATUSES = (
    "AI_GENERATED",
    "DRAFT",
    "VALIDATED",
    "READY_FOR_REVIEW",
    "PARTIALLY_APPROVED",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
)

PROTOCOLS = (
    "CAN",
    "CAN_FD",
    "CAN_XL",
    "LIN",
    "FLEXRAY",
    "ETHERNET",
    "SOME_IP",
    "TCP",
    "UDP",
    "DDS",
    "ROS_2",
    "OPC_UA",
    "ETHERCAT",
    "PROFINET",
    "MODBUS",
    "ARINC",
    "MIL_STD_1553",
    "CUSTOM",
)

PRIORITIES = ("LOW", "NORMAL", "HIGH", "CRITICAL")
REDUNDANCY_MODES = ("NONE", "PRIMARY", "SECONDARY", "BACKUP", "REDUNDANT_ACTIVE", "REDUNDANT_STANDBY")


def _object(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise EngineeringValidationError(f"{field} muss ein Objekt sein.")
    return deepcopy(value)


def _list(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EngineeringValidationError(f"{field} muss eine Liste sein.")
    return deepcopy(value)


def _choice(value: Any, allowed: tuple[str, ...], field: str, default: str) -> str:
    normalized = str(value or default).upper()
    if normalized not in allowed:
        raise EngineeringValidationError(
            f"Ungültiger Wert für {field!r}: {normalized!r}. Erlaubt: {', '.join(allowed)}."
        )
    return normalized


def normalize_route(data: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a complete, validated routing aggregate without resolving references."""
    base = deepcopy(existing or {})
    base.update(deepcopy(data))
    name = str(base.get("name") or "").strip()
    if not name:
        raise EngineeringValidationError("Pflichtfeld fehlt: 'name'.")

    source = _object(base.get("source"), "source")
    destinations = _list(base.get("destinations"), "destinations")
    if not source.get("node_id"):
        raise EngineeringValidationError("source.node_id ist erforderlich.")
    if not destinations or any(not isinstance(item, dict) or not item.get("node_id") for item in destinations):
        raise EngineeringValidationError("Mindestens ein Ziel mit destinations[].node_id ist erforderlich.")

    payload = _object(base.get("payload"), "payload")
    payload["signal_ids"] = _list(payload.get("signal_ids"), "payload.signal_ids")
    message_ids = _list(payload.get("message_ids"), "payload.message_ids")
    if payload.get("message_id"):
        message_ids.insert(0, payload["message_id"])
    payload["message_ids"] = list(dict.fromkeys(str(item) for item in message_ids if item))
    payload["message_id"] = payload["message_ids"][0] if payload["message_ids"] else None
    interface_definition_ids = _list(
        payload.get("interface_definition_ids"),
        "payload.interface_definition_ids",
    )
    if payload.get("interface_definition_id"):
        interface_definition_ids.insert(0, payload["interface_definition_id"])
    payload["interface_definition_ids"] = list(
        dict.fromkeys(str(item) for item in interface_definition_ids if item)
    )
    payload["interface_definition_id"] = (
        payload["interface_definition_ids"][0]
        if payload["interface_definition_ids"]
        else None
    )
    route = _object(base.get("route"), "route")
    route["hops"] = _list(route.get("hops"), "route.hops")
    route["gateways"] = _list(route.get("gateways"), "route.gateways")
    route["transformations"] = _list(route.get("transformations"), "route.transformations")
    route["priority"] = _choice(route.get("priority"), PRIORITIES, "route.priority", "NORMAL")

    timing = _object(base.get("timing"), "timing")
    for field in ("cycle_time_ms", "timeout_ms", "max_latency_ms", "jitter_limit_ms"):
        value = timing.get(field)
        if value in (None, ""):
            timing[field] = None
            continue
        try:
            timing[field] = float(value)
        except (TypeError, ValueError) as error:
            raise EngineeringValidationError(f"timing.{field} muss numerisch sein.") from error
        if timing[field] <= 0:
            raise EngineeringValidationError(f"timing.{field} muss größer als 0 sein.")

    policy = _object(base.get("routing_policy"), "routing_policy")
    policy["routing_type"] = _choice(
        policy.get("routing_type"), ROUTING_TYPES, "routing_policy.routing_type", "UNICAST"
    )
    policy["redundancy"] = _choice(
        policy.get("redundancy"), REDUNDANCY_MODES, "routing_policy.redundancy", "NONE"
    )
    policy["conditions"] = _list(policy.get("conditions"), "routing_policy.conditions")

    origin = _choice(base.get("origin"), ROUTING_ORIGINS, "origin", "MANUAL")
    status = _choice(base.get("status"), ROUTE_STATUSES, "status", "DRAFT")
    confidence = base.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as error:
            raise EngineeringValidationError("confidence muss numerisch sein.") from error
        if not 0 <= confidence <= 1:
            raise EngineeringValidationError("confidence muss zwischen 0 und 1 liegen.")

    return {
        "name": name,
        "description": str(base.get("description") or "").strip() or None,
        "source": source,
        "payload": payload,
        "destinations": destinations,
        "route": route,
        "timing": timing,
        "routing_policy": policy,
        "validation": _object(base.get("validation"), "validation"),
        "status": status,
        "origin": origin,
        "confidence": confidence,
        "review_state": _choice(
            base.get("review_state"), ROUTING_REVIEW_STATES, "review_state", "UNREVIEWED"
        ),
        "approval_state": _choice(
            base.get("approval_state"), ROUTING_APPROVAL_STATES, "approval_state", "PENDING"
        ),
        "source_id": base.get("source_id"),
        "source_version": base.get("source_version"),
        "created_by": base.get("created_by") or base.get("actor"),
        "modified_by": base.get("modified_by") or base.get("actor"),
    }
