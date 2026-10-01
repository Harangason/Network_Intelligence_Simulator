"""Industry-neutral logical diagnostic addressing for canonical HardwareNodes.

This module is the only place that allocates or validates logical node
addresses.  Protocol-specific identifiers remain in technology bindings.
"""

from __future__ import annotations

import re
import uuid
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .db import get_connection, mark_model_changed
from .models import EngineeringValidationError, validate_uuid
from .project_context import current_project_id

MIN_LOGICAL_ADDRESS = 0x0001
MAX_LOGICAL_ADDRESS = 0xFFFE
UNASSIGNED_LOGICAL_ADDRESS = 0x0000
RESERVED_LOGICAL_ADDRESS = 0xFFFF
ASSIGNMENT_STRATEGIES = {"SEQUENTIAL", "LOWEST_FREE", "DOMAIN_RANGE", "DEVICE_CLASS_RANGE", "MANUAL"}
ASSIGNMENT_MODES = {"AUTO", "MANUAL", "IMPORTED", "RESERVED"}


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


def format_logical_node_address(value: int) -> str:
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise EngineeringValidationError("Die Diagnoseadresse muss ein 16-Bit-Wert sein.")
    return f"0x{value:04X}"


def parse_logical_node_address(value: Any) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{1,4}", text):
            raise EngineeringValidationError(
                "Diagnoseadresse muss aus ein bis vier Hex-Stellen bestehen, z. B. 0x0012."
            )
        parsed = int(text.removeprefix("0x").removeprefix("0X"), 16)
    else:
        raise EngineeringValidationError("Diagnoseadresse muss als Hex-Text oder Integer angegeben werden.")
    if not 0 <= parsed <= 0xFFFF:
        raise EngineeringValidationError("Diagnoseadresse liegt außerhalb des 16-Bit-Adressraums.")
    return parsed


@dataclass(frozen=True)
class LogicalNodeAddress:
    value: int
    namespace: str = "PROJECT"
    assignment_mode: str = "AUTO"
    status: str = "ASSIGNED"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parsed = parse_logical_node_address(self.value)
        object.__setattr__(self, "value", parsed)
        object.__setattr__(self, "namespace", str(self.namespace or "PROJECT").upper())
        object.__setattr__(self, "assignment_mode", str(self.assignment_mode or "AUTO").upper())
        object.__setattr__(self, "status", str(self.status or "ASSIGNED").upper())

    @property
    def formatted_value(self) -> str:
        return format_logical_node_address(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "formatted_value": self.formatted_value}


@dataclass(frozen=True)
class AddressPolicy:
    minimum_assignable: int = MIN_LOGICAL_ADDRESS
    maximum_assignable: int = MAX_LOGICAL_ADDRESS
    reserved_ranges: tuple[tuple[int, int], ...] = ()
    assignment_strategy: str = "LOWEST_FREE"
    reuse_policy: str = "REUSE_RELEASED"
    domain_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    device_class_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    device_class_policy: dict[str, bool] = field(
        default_factory=lambda: {"0": False, "1": False, "2": False, "3": False, "4": True}
    )

    def __post_init__(self) -> None:
        if not MIN_LOGICAL_ADDRESS <= self.minimum_assignable <= self.maximum_assignable <= MAX_LOGICAL_ADDRESS:
            raise EngineeringValidationError("AddressPolicy muss innerhalb 0x0001 ... 0xFFFE liegen.")
        strategy = str(self.assignment_strategy or "LOWEST_FREE").upper()
        if strategy not in ASSIGNMENT_STRATEGIES:
            raise EngineeringValidationError(f"Unbekannte Zuweisungsstrategie: {strategy}")
        object.__setattr__(self, "assignment_strategy", strategy)
        normalized = []
        for start, end in self.reserved_ranges:
            left, right = parse_logical_node_address(start), parse_logical_node_address(end)
            if left > right:
                raise EngineeringValidationError("Reservierter Adressbereich beginnt nach seinem Ende.")
            normalized.append((left, right))
        object.__setattr__(self, "reserved_ranges", tuple(normalized))
        for field_name in ("domain_ranges", "device_class_ranges"):
            range_map = {}
            for key, item in getattr(self, field_name).items():
                if isinstance(item, dict):
                    start, end = item.get("start"), item.get("end")
                else:
                    start, end = item
                left, right = parse_logical_node_address(start), parse_logical_node_address(end)
                if not MIN_LOGICAL_ADDRESS <= left <= right <= MAX_LOGICAL_ADDRESS:
                    raise EngineeringValidationError(f"Ungültiger Bereich in {field_name}: {key}")
                range_map[str(key).upper()] = (left, right)
            object.__setattr__(self, field_name, range_map)

    def is_reserved(self, value: int) -> bool:
        return value in {UNASSIGNED_LOGICAL_ADDRESS, RESERVED_LOGICAL_ADDRESS} or any(
            start <= value <= end for start, end in self.reserved_ranges
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reserved_ranges"] = [
            {"start": format_logical_node_address(start), "end": format_logical_node_address(end)}
            for start, end in self.reserved_ranges
        ]
        for field_name in ("domain_ranges", "device_class_ranges"):
            data[field_name] = {
                key: {"start": format_logical_node_address(value[0]), "end": format_logical_node_address(value[1])}
                for key, value in getattr(self, field_name).items()
            }
        return data


def default_addressability_for_class(device_class: Any) -> bool:
    try:
        return int(device_class) == 4
    except (TypeError, ValueError):
        return False


def _policy_from_row(row: dict[str, Any] | None) -> AddressPolicy:
    if not row:
        return AddressPolicy()
    ranges = []
    for item in row.get("reserved_ranges") or []:
        if isinstance(item, dict):
            ranges.append((item.get("start"), item.get("end")))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            ranges.append((item[0], item[1]))
    return AddressPolicy(
        minimum_assignable=int(row.get("minimum_assignable") or MIN_LOGICAL_ADDRESS),
        maximum_assignable=int(row.get("maximum_assignable") or MAX_LOGICAL_ADDRESS),
        reserved_ranges=tuple(ranges),
        assignment_strategy=str(row.get("assignment_strategy") or "LOWEST_FREE"),
        reuse_policy=str(row.get("reuse_policy") or "REUSE_RELEASED"),
        domain_ranges=dict(row.get("domain_ranges") or {}),
        device_class_ranges=dict(row.get("device_class_ranges") or {}),
        device_class_policy={str(key): bool(value) for key, value in (row.get("device_class_policy") or {}).items()},
    )


class LogicalNodeAddressAllocator:
    def __init__(self, project_id: str | None = None, namespace: str = "PROJECT"):
        self.project_id = project_id or current_project_id()
        self.namespace = str(namespace or "PROJECT").upper()

    def _scope(self, connection=None):
        return nullcontext(connection) if connection is not None else get_connection()

    def policy(self, connection=None) -> AddressPolicy:
        with self._scope(connection) as conn:
            row = conn.execute(
                "SELECT * FROM engineering_address_policies WHERE project_id = %s",
                (self.project_id,),
            ).fetchone()
        return _policy_from_row(row)

    def update_policy(self, data: dict[str, Any], *, actor: str | None = None) -> dict[str, Any]:
        current = self.policy()
        raw_ranges = data.get("reserved_ranges")
        ranges = current.reserved_ranges if raw_ranges is None else tuple(
            (item.get("start"), item.get("end")) if isinstance(item, dict) else tuple(item)
            for item in raw_ranges
        )
        policy = AddressPolicy(
            minimum_assignable=parse_logical_node_address(data.get("minimum_assignable", current.minimum_assignable)),
            maximum_assignable=parse_logical_node_address(data.get("maximum_assignable", current.maximum_assignable)),
            reserved_ranges=ranges,
            assignment_strategy=str(data.get("assignment_strategy", current.assignment_strategy)),
            reuse_policy=str(data.get("reuse_policy", current.reuse_policy)),
            domain_ranges=data.get("domain_ranges", current.domain_ranges),
            device_class_ranges=data.get("device_class_ranges", current.device_class_ranges),
            device_class_policy=data.get("device_class_policy", current.device_class_policy),
        )
        with get_connection() as conn:
            row = conn.execute(
                "INSERT INTO engineering_address_policies "
                "(project_id, minimum_assignable, maximum_assignable, reserved_ranges, assignment_strategy, reuse_policy, domain_ranges, device_class_ranges, device_class_policy, modified_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (project_id) DO UPDATE SET "
                "minimum_assignable=EXCLUDED.minimum_assignable, maximum_assignable=EXCLUDED.maximum_assignable, "
                "reserved_ranges=EXCLUDED.reserved_ranges, assignment_strategy=EXCLUDED.assignment_strategy, "
                "reuse_policy=EXCLUDED.reuse_policy, domain_ranges=EXCLUDED.domain_ranges, device_class_ranges=EXCLUDED.device_class_ranges, device_class_policy=EXCLUDED.device_class_policy, "
                "modified_by=EXCLUDED.modified_by, modified_at=now() RETURNING *",
                (
                    self.project_id, policy.minimum_assignable, policy.maximum_assignable,
                    Jsonb([{"start": start, "end": end} for start, end in policy.reserved_ranges]),
                    policy.assignment_strategy, policy.reuse_policy, Jsonb(policy.domain_ranges),
                    Jsonb(policy.device_class_ranges), Jsonb(policy.device_class_policy), actor,
                ),
            ).fetchone()
            self._audit(conn, None, "ADDRESS_POLICY_CHANGED", actor, None, row)
        mark_model_changed()
        return _policy_from_row(row).to_dict()

    def inspect_existing_addresses(self, connection=None) -> list[dict[str, Any]]:
        with self._scope(connection) as conn:
            rows = conn.execute(
                "SELECT id, name, device_type, device_class, diagnostic_addressable, logical_node_address, "
                "address_assignment_mode, address_status, address_namespace, address_provenance "
                "FROM engineering_hardware_nodes WHERE project_id = %s AND address_namespace = %s "
                "ORDER BY logical_node_address NULLS LAST, name",
                (self.project_id, self.namespace),
            ).fetchall()
        return [self._decorate(row) for row in rows]

    def find_next_free_address(self, connection=None, *, node: dict[str, Any] | None = None) -> LogicalNodeAddress:
        with self._scope(connection) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"logical-address:{self.project_id}:{self.namespace}",))
            policy = self.policy(conn)
            if policy.assignment_strategy == "MANUAL":
                raise EngineeringValidationError("Die Projektpolicy verlangt eine manuelle Diagnoseadresse.")
            used = {
                int(row["logical_node_address"])
                for row in conn.execute(
                    "SELECT logical_node_address FROM engineering_hardware_nodes "
                    "WHERE project_id = %s AND address_namespace = %s AND logical_node_address IS NOT NULL",
                    (self.project_id, self.namespace),
                ).fetchall()
            }
            if policy.reuse_policy.upper() in {"NEVER_REUSE", "NO_REUSE"}:
                used.update(
                    int(row["logical_node_address"])
                    for row in conn.execute(
                        "SELECT DISTINCT (after_state->>'logical_node_address')::integer AS logical_node_address "
                        "FROM engineering_address_audit WHERE project_id=%s AND after_state ? 'logical_node_address' "
                        "AND (after_state->>'logical_node_address') ~ '^[0-9]+$'",
                        (self.project_id,),
                    ).fetchall()
                )
            lower, upper = policy.minimum_assignable, policy.maximum_assignable
            if node and policy.assignment_strategy == "DOMAIN_RANGE":
                lower, upper = policy.domain_ranges.get(str(node.get("domain") or "").upper(), (lower, upper))
            if node and policy.assignment_strategy == "DEVICE_CLASS_RANGE":
                lower, upper = policy.device_class_ranges.get(str(node.get("device_class") or "").upper(), (lower, upper))
            lower, upper = max(lower, policy.minimum_assignable), min(upper, policy.maximum_assignable)
            candidates = range(lower, upper + 1)
            if policy.assignment_strategy == "SEQUENTIAL" and used:
                start = max(used) + 1
                candidates = range(max(start, lower), upper + 1)
            for candidate in candidates:
                if candidate not in used and not policy.is_reserved(candidate):
                    return LogicalNodeAddress(candidate, self.namespace, "AUTO", "PROPOSED", {"allocator": "python"})
        raise EngineeringValidationError("Kein freier logischer Diagnoseadresswert verfügbar.")

    def validate_address(self, value: Any, *, node_id: str | None = None, connection=None) -> dict[str, Any]:
        parsed = parse_logical_node_address(value)
        policy = self.policy(connection)
        errors = []
        if parsed == UNASSIGNED_LOGICAL_ADDRESS:
            errors.append({"code": "DIAGNOSTIC_ADDRESS_INVALID", "message": "0x0000 ist UNASSIGNED/INVALID."})
        if parsed != UNASSIGNED_LOGICAL_ADDRESS and policy.is_reserved(parsed):
            errors.append({"code": "DIAGNOSTIC_ADDRESS_RESERVED", "message": f"{format_logical_node_address(parsed)} ist reserviert."})
        if not policy.minimum_assignable <= parsed <= policy.maximum_assignable:
            errors.append({"code": "DIAGNOSTIC_ADDRESS_INVALID", "message": "Adresse liegt außerhalb der Projektpolicy."})
        with self._scope(connection) as conn:
            if node_id:
                row = conn.execute(
                    "SELECT id, name FROM engineering_hardware_nodes WHERE project_id=%s AND address_namespace=%s "
                    "AND logical_node_address=%s AND id::text<>%s LIMIT 1",
                    (self.project_id, self.namespace, parsed, node_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, name FROM engineering_hardware_nodes WHERE project_id=%s AND address_namespace=%s "
                    "AND logical_node_address=%s LIMIT 1",
                    (self.project_id, self.namespace, parsed),
                ).fetchone()
        if row:
            errors.append({"code": "DIAGNOSTIC_ADDRESS_CONFLICT", "message": f"Adresse ist bereits {row['name']} zugeordnet.", "object_id": str(row["id"])})
        return {"valid": not errors, "value": parsed, "formatted_value": format_logical_node_address(parsed), "namespace": self.namespace, "errors": errors}

    def assign_address(
        self,
        node_id: str,
        value: Any | None = None,
        *,
        assignment_mode: str = "AUTO",
        actor: str | None = None,
        connection=None,
        increment_version: bool = True,
    ) -> dict[str, Any]:
        validate_uuid(node_id)
        mode = str(assignment_mode or "AUTO").upper()
        if mode not in ASSIGNMENT_MODES:
            raise EngineeringValidationError(f"Unbekannter Assignment Mode: {mode}")
        with self._scope(connection) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"logical-address:{self.project_id}:{self.namespace}",))
            before = conn.execute(
                "SELECT * FROM engineering_hardware_nodes WHERE id=%s AND project_id=%s FOR UPDATE",
                (node_id, self.project_id),
            ).fetchone()
            if not before:
                raise EngineeringValidationError(f"HardwareNode {node_id} wurde nicht gefunden.")
            policy = self.policy(conn)
            provenance = dict(before.get("address_provenance") or {})
            if provenance.get("addressability_source") != "explicit":
                addressable = bool(policy.device_class_policy.get(str(before.get("device_class")), False))
            else:
                addressable = bool(before.get("diagnostic_addressable"))
            if not addressable:
                return self._decorate(before)
            proposed = self.find_next_free_address(conn, node=before).value if value is None else parse_logical_node_address(value)
            validation = self.validate_address(proposed, node_id=node_id, connection=conn)
            if not validation["valid"]:
                self._audit(conn, node_id, "ADDRESS_CONFLICT_DETECTED", actor, before, None, {"validation": validation})
                raise EngineeringValidationError(validation["errors"][0]["message"])
            self._audit(
                conn, node_id, "ADDRESS_PROPOSED", actor, before, None,
                {"value": proposed, "formatted_value": format_logical_node_address(proposed), "namespace": self.namespace},
            )
            provenance.update({"allocator": "LogicalNodeAddressAllocator", "actor": actor, "assignment_mode": mode})
            try:
                after = conn.execute(
                    "UPDATE engineering_hardware_nodes SET diagnostic_addressable=TRUE, logical_node_address=%s, "
                    "address_assignment_mode=%s, address_status='ASSIGNED', address_namespace=%s, address_provenance=%s, "
                    "version=version+%s, modified_at=now(), modified_by=%s WHERE id=%s AND project_id=%s RETURNING *",
                    (proposed, mode, self.namespace, Jsonb(provenance), 1 if increment_version else 0,
                     actor, node_id, self.project_id),
                ).fetchone()
            except UniqueViolation as error:
                raise EngineeringValidationError("DIAGNOSTIC_ADDRESS_CONFLICT: Adresse ist im Namespace bereits vergeben.") from error
            event = "ADDRESS_ASSIGNED" if before.get("logical_node_address") is None else "ADDRESS_CHANGED"
            self._audit(conn, node_id, event, actor, before, after)
            if event == "ADDRESS_CHANGED":
                self._mark_dependents_outdated(conn, node_id, before, after, actor)
        mark_model_changed()
        return self._decorate(after)

    def release_address(self, node_id: str, *, actor: str | None = None) -> dict[str, Any]:
        validate_uuid(node_id)
        with get_connection() as conn:
            before = conn.execute("SELECT * FROM engineering_hardware_nodes WHERE id=%s AND project_id=%s FOR UPDATE", (node_id, self.project_id)).fetchone()
            if not before:
                raise EngineeringValidationError(f"HardwareNode {node_id} wurde nicht gefunden.")
            after = conn.execute(
                "UPDATE engineering_hardware_nodes SET logical_node_address=NULL, address_status='UNASSIGNED', "
                "version=version+1, modified_at=now(), modified_by=%s WHERE id=%s AND project_id=%s RETURNING *",
                (actor, node_id, self.project_id),
            ).fetchone()
            self._audit(conn, node_id, "ADDRESS_RELEASED", actor, before, after)
            self._mark_dependents_outdated(conn, node_id, before, after, actor)
        mark_model_changed()
        return self._decorate(after)

    def impact_analysis(self, node_id: str, proposed_value: Any | None = None) -> dict[str, Any]:
        validate_uuid(node_id)
        with get_connection() as conn:
            node = conn.execute(
                "SELECT id, name, logical_node_address, address_namespace FROM engineering_hardware_nodes "
                "WHERE id=%s AND project_id=%s",
                (node_id, self.project_id),
            ).fetchone()
            if not node:
                raise EngineeringValidationError(f"HardwareNode {node_id} wurde nicht gefunden.")
            validation = self.validate_address(proposed_value, node_id=node_id, connection=conn) if proposed_value not in (None, "") else None
            routes = conn.execute(
                "SELECT count(*) AS count FROM engineering_routing_entries WHERE project_id=%s "
                "AND (source->>'node_id'=%s OR EXISTS (SELECT 1 FROM jsonb_array_elements(destinations) d WHERE d->>'node_id'=%s))",
                (self.project_id, node_id, node_id),
            ).fetchone()["count"]
            bindings = conn.execute(
                "SELECT count(*) AS count FROM engineering_technology_address_bindings WHERE project_id=%s AND hardware_node_id=%s",
                (self.project_id, node_id),
            ).fetchone()["count"]
            snapshots = conn.execute(
                "SELECT count(*) AS count FROM engineering_simulation_snapshots WHERE project_id=%s AND is_outdated=FALSE",
                (self.project_id,),
            ).fetchone()["count"]
            traces = conn.execute(
                "SELECT count(*) AS count FROM engineering_trace_metadata WHERE project_id=%s "
                "AND COALESCE((trace_summary->>'is_outdated')::boolean, FALSE)=FALSE",
                (self.project_id,),
            ).fetchone()["count"]
        return {
            "hardware_node_id": node_id,
            "hardware_node_name": node.get("name"),
            "current_address": format_logical_node_address(int(node["logical_node_address"])) if node.get("logical_node_address") is not None else None,
            "proposed_address": validation.get("formatted_value") if validation else None,
            "validation": validation,
            "affected": {"routing_entries": int(routes), "simulation_snapshots": int(snapshots), "trace_references": int(traces), "technology_bindings": int(bindings)},
            "effects": ["Routing -> OUTDATED", "Simulation snapshots -> OUTDATED", "Trace references -> OUTDATED", "Technology bindings -> OUTDATED"],
            "confirmation_required": True,
        }

    def reserve_address(self, value: Any, *, actor: str | None = None) -> dict[str, Any]:
        parsed = parse_logical_node_address(value)
        policy = self.policy()
        if parsed in {UNASSIGNED_LOGICAL_ADDRESS, RESERVED_LOGICAL_ADDRESS}:
            return {"reserved": format_logical_node_address(parsed), "policy": policy.to_dict()}
        ranges = [*policy.reserved_ranges, (parsed, parsed)]
        result = self.update_policy({"reserved_ranges": ranges}, actor=actor)
        with get_connection() as conn:
            self._audit(conn, None, "ADDRESS_RESERVED", actor, None, None, {"address": parsed})
        return {"reserved": format_logical_node_address(parsed), "policy": result}

    def detect_conflicts(self, connection=None) -> list[dict[str, Any]]:
        with self._scope(connection) as conn:
            rows = conn.execute(
                "SELECT address_namespace, logical_node_address, count(*) AS count, array_agg(id::text) AS node_ids "
                "FROM engineering_hardware_nodes WHERE project_id=%s AND logical_node_address IS NOT NULL "
                "GROUP BY address_namespace, logical_node_address HAVING count(*) > 1",
                (self.project_id,),
            ).fetchall()
        return [{**row, "formatted_value": format_logical_node_address(int(row["logical_node_address"]))} for row in rows]

    def findings(self) -> list[dict[str, Any]]:
        policy = self.policy()
        findings = []
        nodes = self.inspect_existing_addresses()
        with get_connection() as conn:
            binding_counts = {
                str(row["hardware_node_id"]): int(row["count"])
                for row in conn.execute(
                    "SELECT hardware_node_id, count(*) AS count FROM engineering_technology_address_bindings "
                    "WHERE project_id=%s AND status='ASSIGNED' GROUP BY hardware_node_id",
                    (self.project_id,),
                ).fetchall()
            }
            routes = conn.execute(
                "SELECT id, route_code, source, destinations FROM engineering_routing_entries "
                "WHERE project_id=%s AND status NOT IN ('REJECTED','SUPERSEDED','DEPRECATED')",
                (self.project_id,),
            ).fetchall()
        address_by_node = {
            str(node["id"]): (bool(node.get("diagnostic_addressable")), node.get("logical_node_address"))
            for node in nodes
        }
        for node in nodes:
            value = node.get("logical_node_address")
            if node.get("diagnostic_addressable") and value is None:
                findings.append(self._finding("DIAGNOSTIC_ADDRESS_MISSING", node, "Adressierbarer HardwareNode besitzt keine Diagnoseadresse."))
            elif value is not None:
                if value == UNASSIGNED_LOGICAL_ADDRESS or not policy.minimum_assignable <= value <= policy.maximum_assignable:
                    findings.append(self._finding("DIAGNOSTIC_ADDRESS_INVALID", node, "Diagnoseadresse ist ungültig."))
                elif policy.is_reserved(value):
                    findings.append(self._finding("DIAGNOSTIC_ADDRESS_RESERVED", node, "Diagnoseadresse liegt in einem reservierten Bereich."))
            if node.get("address_status") == "OUTDATED":
                findings.append(self._finding("DIAGNOSTIC_ADDRESS_OUTDATED", node, "Diagnoseadresse oder abhängige Ergebnisse sind veraltet."))
            if node.get("diagnostic_addressable") and value is not None:
                binding_required = bool((node.get("address_provenance") or {}).get("technology_binding_required"))
                if binding_required and not binding_counts.get(str(node["id"])):
                    findings.append(self._finding("ADDRESS_BINDING_MISSING", node, "Keine technologiespezifische Adressbindung vorhanden.", severity="WARNING"))
        for conflict in self.detect_conflicts():
            findings.append({"code": "DIAGNOSTIC_ADDRESS_CONFLICT", "severity": "ERROR", "message": "Diagnoseadresse ist mehrfach vergeben.", **conflict})
        for route in routes:
            endpoint_ids = [
                str(route.get("source", {}).get("node_id") or ""),
                *(str(item.get("node_id") or "") for item in route.get("destinations") or []),
            ]
            unresolved = [
                node_id for node_id in endpoint_ids
                if node_id and address_by_node.get(node_id, (False, None))[0]
                and address_by_node.get(node_id, (False, None))[1] is None
            ]
            if unresolved:
                findings.append({
                    "code": "ADDRESS_ROUTE_UNRESOLVED",
                    "severity": "ERROR",
                    "message": "Mindestens ein Routenendpunkt besitzt keine auflösbare logische Diagnoseadresse.",
                    "object_type": "RoutingEntry",
                    "object_id": str(route["id"]),
                    "object_name": route.get("route_code"),
                    "unresolved_node_ids": unresolved,
                })
        return findings

    def _finding(self, code: str, node: dict[str, Any], message: str, *, severity: str = "ERROR") -> dict[str, Any]:
        return {"code": code, "severity": severity, "message": message, "object_type": "HardwareNode", "object_id": str(node["id"]), "object_name": node.get("name")}

    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        value = result.get("logical_node_address")
        result["formatted_logical_node_address"] = format_logical_node_address(int(value)) if value is not None else None
        result["logical_node_address_object"] = (
            LogicalNodeAddress(
                int(value), result.get("address_namespace") or self.namespace,
                result.get("address_assignment_mode") or "AUTO", result.get("address_status") or "ASSIGNED",
                dict(result.get("address_provenance") or {}),
            ).to_dict() if value is not None else None
        )
        return result

    def _audit(self, conn, node_id, event_type, actor, before, after, details=None) -> None:
        # Repository and MCP callers may create the first canonical object
        # before they explicitly open the workflow view.  The audit FK must
        # not make that otherwise valid creation path order-dependent.
        conn.execute(
            "INSERT INTO engineering_workflow_projects (project_id) VALUES (%s) "
            "ON CONFLICT (project_id) DO NOTHING",
            (self.project_id,),
        )
        conn.execute(
            "INSERT INTO engineering_address_audit (project_id, hardware_node_id, event_type, actor, before_state, after_state, details) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (self.project_id, node_id, event_type, actor, Jsonb(_json_safe(before)) if before else None, Jsonb(_json_safe(after)) if after else None, Jsonb(_json_safe(details or {}))),
        )

    def _mark_dependents_outdated(self, conn, node_id, before, after, actor) -> None:
        reason = f"Diagnoseadresse von {before.get('name')} wurde geändert."
        routes = conn.execute(
            "SELECT * FROM engineering_routing_entries WHERE project_id=%s AND (source->>'node_id'=%s OR EXISTS (SELECT 1 FROM jsonb_array_elements(destinations) d WHERE d->>'node_id'=%s)) FOR UPDATE",
            (self.project_id, node_id, node_id),
        ).fetchall()
        for route in routes:
            validation = dict(route.get("validation") or {})
            warnings = [item for item in validation.get("warnings") or [] if item.get("code") != "DIAGNOSTIC_ADDRESS_OUTDATED"]
            warnings.append({"code": "DIAGNOSTIC_ADDRESS_OUTDATED", "message": reason})
            validation.update({"valid": False, "warnings": warnings, "outdated_reason": reason})
            conn.execute(
                "UPDATE engineering_routing_entries SET status='OUTDATED', approval_state='PENDING', review_state='IN_REVIEW', validation=%s, modified_by=%s, modified_at=now() WHERE id=%s",
                (Jsonb(validation), actor, route["id"]),
            )
        conn.execute(
            "UPDATE engineering_simulation_snapshots SET is_outdated=TRUE, outdated_reason=%s, updated_at=now() WHERE project_id=%s AND is_outdated=FALSE",
            (reason, self.project_id),
        )
        conn.execute(
            "UPDATE engineering_trace_metadata SET trace_summary=trace_summary || %s WHERE project_id=%s",
            (Jsonb({"is_outdated": True, "outdated_reason": reason}), self.project_id),
        )
        conn.execute(
            "UPDATE engineering_technology_address_bindings SET logical_node_address=COALESCE(%s, logical_node_address), "
            "status='OUTDATED', modified_at=now() WHERE project_id=%s AND hardware_node_id=%s",
            (after.get("logical_node_address") if after else None, self.project_id, node_id),
        )


class AddressResolutionService:
    def __init__(self, project_id: str | None = None, namespace: str = "PROJECT"):
        self.project_id = project_id or current_project_id()
        self.namespace = str(namespace or "PROJECT").upper()
        self.allocator = LogicalNodeAddressAllocator(self.project_id, self.namespace)

    def resolve_node(self, address: Any) -> dict[str, Any]:
        parsed = parse_logical_node_address(address)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM engineering_hardware_nodes WHERE project_id=%s AND address_namespace=%s AND logical_node_address=%s",
                (self.project_id, self.namespace, parsed),
            ).fetchone()
        if not row:
            raise EngineeringValidationError(f"ADDRESS_ROUTE_UNRESOLVED: {format_logical_node_address(parsed)} ist nicht zugeordnet.")
        return self.allocator._decorate(row)

    def resolve_address(self, node_ref: str) -> dict[str, Any]:
        validate_uuid(node_ref)
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM engineering_hardware_nodes WHERE project_id=%s AND id=%s", (self.project_id, node_ref)).fetchone()
        if not row:
            raise EngineeringValidationError(f"HardwareNode {node_ref} wurde nicht gefunden.")
        return self.allocator._decorate(row)

    def resolve_interfaces(self, address: Any) -> list[dict[str, Any]]:
        node = self.resolve_node(address)
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM engineering_hardware_interfaces WHERE project_id=%s AND hardware_node_id=%s ORDER BY channel_index, name",
                (self.project_id, node["id"]),
            ).fetchall()

    def resolve_networks(self, address: Any) -> list[dict[str, Any]]:
        return [
            {"network_ref": item.get("network_ref"), "technology": item.get("technology"), "hardware_interface_id": str(item["id"])}
            for item in self.resolve_interfaces(address) if item.get("network_ref")
        ]

    def resolve_routes(self, source_address: Any, destination_address: Any) -> list[dict[str, Any]]:
        source, destination = self.resolve_node(source_address), self.resolve_node(destination_address)
        with get_connection() as conn:
            routes = conn.execute(
                "SELECT * FROM engineering_routing_entries WHERE project_id=%s AND source->>'node_id'=%s "
                "AND EXISTS (SELECT 1 FROM jsonb_array_elements(destinations) d WHERE d->>'node_id'=%s) ORDER BY revision DESC",
                (self.project_id, str(source["id"]), str(destination["id"])),
            ).fetchall()
        return routes

    def resolve(self, address: Any) -> dict[str, Any]:
        node = self.resolve_node(address)
        interfaces = self.resolve_interfaces(address)
        with get_connection() as conn:
            bindings = conn.execute(
                "SELECT * FROM engineering_technology_address_bindings "
                "WHERE project_id=%s AND hardware_node_id=%s ORDER BY technology, technology_address",
                (self.project_id, node["id"]),
            ).fetchall()
            routes = conn.execute(
                "SELECT * FROM engineering_routing_entries WHERE project_id=%s "
                "AND (source->>'node_id'=%s OR EXISTS "
                "(SELECT 1 FROM jsonb_array_elements(destinations) d WHERE d->>'node_id'=%s)) "
                "ORDER BY revision DESC",
                (self.project_id, str(node["id"]), str(node["id"])),
            ).fetchall()
        return {
            "address": node["logical_node_address_object"],
            "node": node,
            "interfaces": interfaces,
            "networks": self.resolve_networks(address),
            "technology_bindings": bindings,
            "routes": routes,
        }


def create_technology_address_binding(data: dict[str, Any], *, actor: str | None = None) -> dict[str, Any]:
    node_id = str(data.get("hardware_node_id") or "")
    node = AddressResolutionService().resolve_address(node_id)
    if node.get("logical_node_address") is None:
        raise EngineeringValidationError("HardwareNode besitzt keine logische Diagnoseadresse.")
    technology_address = str(data.get("technology_address") or "").strip()
    technology = str(data.get("technology") or "").strip().upper()
    if not technology or not technology_address:
        raise EngineeringValidationError("Technologie und technologiespezifische Adresse sind erforderlich.")
    interface_ref = data.get("hardware_interface_ref")
    if interface_ref:
        validate_uuid(str(interface_ref))
    with get_connection() as conn:
        if interface_ref:
            interface = conn.execute(
                "SELECT id FROM engineering_hardware_interfaces WHERE project_id=%s AND id=%s AND hardware_node_id=%s",
                (current_project_id(), interface_ref, node_id),
            ).fetchone()
            if not interface:
                raise EngineeringValidationError("Hardware Interface gehört nicht zum angegebenen HardwareNode.")
        row = conn.execute(
            "INSERT INTO engineering_technology_address_bindings "
            "(project_id, hardware_node_id, logical_node_address, technology, technology_address, hardware_interface_ref, network_ref, status, provenance) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (current_project_id(), node_id, node["logical_node_address"], technology, technology_address,
             interface_ref, data.get("network_ref"), data.get("status") or "ASSIGNED", Jsonb(data.get("provenance") or {"actor": actor})),
        ).fetchone()
        LogicalNodeAddressAllocator()._audit(conn, node_id, "TECHNOLOGY_BINDING_CREATED", actor, None, row)
    mark_model_changed()
    return row
