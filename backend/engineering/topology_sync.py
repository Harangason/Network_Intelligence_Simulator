"""Synchronize the visual network editor with the canonical engineering model."""

from __future__ import annotations

import threading
from collections import Counter
from typing import Any

from psycopg.types.json import Jsonb

from .db import get_connection
from .models import EngineeringValidationError
from .project_context import current_project_id
from .relations import create_relation
from .repository import NotFoundError, create_object, get_object, update_object

NODE_KIND_TO_DEVICE_TYPE = {
    "ecu": "ECU",
    "gateway": "Gateway",
    "sensor": "SensorController",
    "actuator": "ActuatorController",
}

BUS_TO_INTERFACE_TYPE = {
    "can": "CAN",
    "can_fd": "CAN_FD",
    "lin": "LIN",
    "automotive_ethernet": "Ethernet",
    "flexray": "FlexRay",
}

ORIGIN = "network-editor"
_sync_locks: dict[str, threading.Lock] = {}
_sync_locks_guard = threading.Lock()


def _sync_lock(topology_id: str) -> threading.Lock:
    with _sync_locks_guard:
        return _sync_locks.setdefault(topology_id, threading.Lock())


def _text(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise EngineeringValidationError(f"Pflichtfeld fehlt: {field!r}")
    return result


def _find_hardware(topology_id: str, node_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_hardware_nodes "
            "WHERE identity ->> 'topology_id' = %s "
            "AND identity ->> 'topology_node_id' = %s AND project_id = %s",
            (topology_id, node_id, current_project_id()),
        ).fetchone()


def _find_function(topology_id: str, hardware_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_functions "
            "WHERE hardware_node_id = %s AND project_id = %s "
            "ORDER BY CASE WHEN provenance ->> 'origin' = %s "
            "AND provenance ->> 'topology_id' = %s THEN 0 ELSE 1 END, created_at LIMIT 1",
            (hardware_id, current_project_id(), ORIGIN, topology_id),
        ).fetchone()


def _find_interface(topology_id: str, port_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_interfaces "
            "WHERE configuration ->> 'topology_id' = %s "
            "AND configuration ->> 'topology_port_id' = %s AND project_id = %s",
            (topology_id, port_id, current_project_id()),
        ).fetchone()


def _is_generated_interface(interface: dict[str, Any], topology_id: str) -> bool:
    provenance = interface.get("provenance") or {}
    return (
        provenance.get("origin") == ORIGIN
        and provenance.get("topology_id") == topology_id
    )


def _find_preferred_interface(
    hardware_id: str,
    interface_type: str,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_interfaces "
            "WHERE hardware_node_id = %s AND interface_type = %s AND project_id = %s "
            "ORDER BY CASE WHEN provenance ->> 'origin' = %s THEN 1 ELSE 0 END, "
            "created_at, id LIMIT 1",
            (hardware_id, interface_type, current_project_id(), ORIGIN),
        ).fetchone()


def _find_connection(
    source_id: str,
    target_id: str,
    relation_type: str,
    topology_id: str,
    edge_id: str,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_relations "
            "WHERE project_id = %s AND ("
            "(attributes ->> 'topology_id' = %s AND attributes ->> 'topology_edge_id' = %s) OR "
            "(relation_type = %s AND source_type = 'Interface' AND source_id = %s "
            "AND target_type = 'Interface' AND target_id = %s)) "
            "ORDER BY CASE WHEN attributes ->> 'topology_id' = %s "
            "AND attributes ->> 'topology_edge_id' = %s THEN 0 ELSE 1 END LIMIT 1",
            (
                current_project_id(),
                topology_id,
                edge_id,
                relation_type,
                source_id,
                target_id,
                topology_id,
                edge_id,
            ),
        ).fetchone()


def _update_connection_if_changed(
    current: dict[str, Any],
    *,
    relation_type: str,
    source_id: str,
    target_id: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    merged_attributes = {**(current.get("attributes") or {}), **attributes}
    if (
        current.get("relation_type") == relation_type
        and str(current.get("source_id")) == source_id
        and str(current.get("target_id")) == target_id
        and current.get("attributes") == merged_attributes
    ):
        return current

    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_relations SET relation_type = %s, source_id = %s, "
            "target_id = %s, attributes = %s WHERE id = %s AND project_id = %s RETURNING *",
            (
                relation_type,
                source_id,
                target_id,
                Jsonb(merged_attributes),
                current["id"],
                current_project_id(),
            ),
        ).fetchone()
        connection.commit()
    return row


def _update_if_changed(
    object_type: str,
    current: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    def differs(key: str, value: Any) -> bool:
        current_value = current.get(key)
        if isinstance(value, str) and current_value is not None:
            return str(current_value) != value
        return current_value != value

    changes = {key: value for key, value in expected.items() if differs(key, value)}
    if not changes:
        return current
    return update_object(object_type, str(current["id"]), changes)


def sync_topology(data: dict[str, Any]) -> dict[str, Any]:
    topology_id = _text(data.get("topology_id") or "studio-network", "topology_id")
    with _sync_lock(f"{current_project_id()}:{topology_id}"):
        return _sync_topology(data, topology_id)


def _sync_topology(data: dict[str, Any], topology_id: str) -> dict[str, Any]:
    nodes = data.get("nodes")
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise EngineeringValidationError("'nodes' und 'edges' müssen Listen sein.")

    node_ids: set[str] = set()
    port_ids: set[str] = set()
    interface_by_port: dict[str, dict[str, Any]] = {}
    claimed_interface_ports: dict[str, str] = {}
    synchronized_nodes: list[dict[str, Any]] = []
    requested_interface_names: dict[str, str] = {}

    for raw_edge in edges:
        if not isinstance(raw_edge, dict):
            continue
        for port_field, name_field in (
            ("sourcePort", "sourceInterfaceName"),
            ("targetPort", "targetInterfaceName"),
        ):
            port_id = str(raw_edge.get(port_field) or "").strip()
            interface_name = str(raw_edge.get(name_field) or "").strip()
            if not port_id or not interface_name:
                continue
            current_name = requested_interface_names.get(port_id)
            if current_name is not None and current_name != interface_name:
                raise EngineeringValidationError(
                    f"Widerspruechliche Interface-Namen fuer Port {port_id!r}."
                )
            requested_interface_names[port_id] = interface_name

    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            raise EngineeringValidationError("Jeder Netzwerkknoten muss ein Objekt sein.")
        node_id = _text(raw_node.get("id"), "node.id")
        if node_id in node_ids:
            raise EngineeringValidationError(f"Doppelte Knoten-ID: {node_id!r}")
        node_ids.add(node_id)
        name = _text(raw_node.get("name"), "node.name")
        kind = _text(raw_node.get("kind"), "node.kind")
        device_type = NODE_KIND_TO_DEVICE_TYPE.get(kind)
        if device_type is None:
            raise EngineeringValidationError(f"Unbekannter Netzwerkknoten-Typ: {kind!r}")
        provenance = {"origin": ORIGIN, "topology_id": topology_id}
        requested_engineering_id = str(raw_node.get("engineeringId") or "").strip()
        if not requested_engineering_id and node_id.startswith("engineering-"):
            requested_engineering_id = node_id.removeprefix("engineering-")

        hardware = None
        if requested_engineering_id:
            try:
                hardware = get_object("HardwareNode", requested_engineering_id)
            except NotFoundError as error:
                raise EngineeringValidationError(
                    f"Verknüpfter Hardware-Knoten nicht gefunden: {requested_engineering_id!r}"
                ) from error
        if hardware is None:
            hardware = _find_hardware(topology_id, node_id)
        identity = {
            **(hardware.get("identity") if hardware else {}),
            "topology_id": topology_id,
            "topology_node_id": node_id,
        }
        if hardware is None:
            hardware = create_object(
                "HardwareNode",
                {
                    "name": name,
                    "domain": "automotive",
                    "device_type": device_type,
                    "identity": identity,
                    "provenance": provenance,
                },
            )
        else:
            # Existing canonical objects own their human-readable identity. The
            # network editor may link and enrich them, but opening an older
            # topology must never rename the Engineering model backwards.
            hardware_updates = {"identity": identity}
            if (hardware.get("provenance") or {}).get("origin") == ORIGIN:
                hardware_updates["device_type"] = device_type
            hardware = _update_if_changed(
                "HardwareNode",
                hardware,
                hardware_updates,
            )

        function = _find_function(topology_id, str(hardware["id"]))
        canonical_name = str(hardware.get("name") or name)
        function_name = f"{canonical_name} Kommunikation"
        if function is None:
            function = create_object(
                "Function",
                {
                    "name": function_name,
                    "domain": "automotive",
                    "hardware_node_id": str(hardware["id"]),
                    "provenance": provenance,
                },
            )
        elif (function.get("provenance") or {}).get("origin") == ORIGIN:
            function = _update_if_changed("Function", function, {"name": function_name})

        synchronized_ports: list[dict[str, str]] = []
        raw_ports = raw_node.get("ports", [])
        if not isinstance(raw_ports, list):
            raise EngineeringValidationError("'node.ports' muss eine Liste sein.")
        port_name_bases = [
            str(
                requested_interface_names.get(str(raw_port.get("id") or "").strip())
                or raw_port.get("name")
                or BUS_TO_INTERFACE_TYPE.get(str(raw_port.get("bus") or "").strip())
                or "Interface"
            ).strip()
            for raw_port in raw_ports
            if isinstance(raw_port, dict)
        ]
        port_name_counts = Counter(port_name_bases)
        port_name_indexes: Counter[str] = Counter()
        for raw_port in raw_ports:
            if not isinstance(raw_port, dict):
                raise EngineeringValidationError("Jeder Port muss ein Objekt sein.")
            port_id = _text(raw_port.get("id"), "port.id")
            if port_id in port_ids:
                raise EngineeringValidationError(f"Doppelte Port-ID: {port_id!r}")
            port_ids.add(port_id)
            bus = _text(raw_port.get("bus"), "port.bus")
            interface_type = BUS_TO_INTERFACE_TYPE.get(bus)
            if interface_type is None:
                raise EngineeringValidationError(f"Unbekannter Bustyp: {bus!r}")
            port_name_base = _text(
                requested_interface_names.get(port_id)
                or raw_port.get("name")
                or interface_type,
                "port.name",
            )
            port_name_indexes[port_name_base] += 1
            port_name = (
                f"{port_name_base}_{port_name_indexes[port_name_base]}"
                if port_name_counts[port_name_base] > 1
                and port_name_indexes[port_name_base] > 1
                else port_name_base
            )
            configuration = {
                "topology_id": topology_id,
                "topology_node_id": node_id,
                "topology_port_id": port_id,
                "bus": bus,
                "network_id": f"network-{bus}",
            }
            requested_interface_id = str(raw_port.get("engineeringId") or raw_port.get("engineering_id") or "").strip()
            interface = None
            if requested_interface_id:
                try:
                    interface = get_object("Interface", requested_interface_id)
                except NotFoundError as error:
                    raise EngineeringValidationError(
                        f"Verknuepftes Interface nicht gefunden: {requested_interface_id!r}"
                    ) from error
                if str(interface.get("hardware_node_id") or "") != str(hardware["id"]):
                    raise EngineeringValidationError(
                        f"Interface {requested_interface_id!r} gehoert nicht zu {name!r}."
                    )
                if claimed_interface_ports.get(str(interface["id"])) not in (None, port_id):
                    interface = None
            if interface is None:
                interface = _find_interface(topology_id, port_id)
            preferred_interface = _find_preferred_interface(
                str(hardware["id"]),
                interface_type,
            )
            if (
                preferred_interface is not None
                and claimed_interface_ports.get(str(preferred_interface["id"])) not in (None, port_id)
            ):
                preferred_interface = None
            reused_interface = False
            if interface is None and preferred_interface is not None:
                interface = preferred_interface
                reused_interface = True
            elif (
                interface is not None
                and _is_generated_interface(interface, topology_id)
                and preferred_interface is not None
                and str(preferred_interface["id"]) != str(interface["id"])
            ):
                interface = preferred_interface
                reused_interface = True
            elif interface is not None and not _is_generated_interface(interface, topology_id):
                reused_interface = True
            expected_interface = {
                "name": port_name,
                "hardware_node_id": str(hardware["id"]),
                "function_id": str(function["id"]),
                "interface_type": interface_type,
                "configuration": configuration,
            }
            if interface is None:
                interface = create_object(
                    "Interface",
                    {
                        **expected_interface,
                        "domain": "automotive",
                        "provenance": provenance,
                    },
                )
            elif reused_interface:
                reused_changes: dict[str, Any] = {
                    "configuration": {
                        **(interface.get("configuration") or {}),
                        **configuration,
                    }
                }
                if kind == "gateway" and requested_interface_names.get(port_id):
                    reused_changes["name"] = port_name
                interface = _update_if_changed(
                    "Interface",
                    interface,
                    reused_changes,
                )
            elif not reused_interface:
                interface = _update_if_changed("Interface", interface, expected_interface)
            claimed_interface_ports[str(interface["id"])] = port_id
            interface_by_port[port_id] = interface
            synchronized_ports.append(
                {
                    "topology_port_id": port_id,
                    "engineering_id": str(interface["id"]),
                    "engineering_name": str(interface["name"]),
                }
            )

        synchronized_nodes.append(
            {
                "topology_node_id": node_id,
                "engineering_id": str(hardware["id"]),
                "engineering_name": canonical_name,
                "function_id": str(function["id"]),
                "interfaces": synchronized_ports,
            }
        )

    synchronized_edges: list[dict[str, str]] = []
    for raw_edge in edges:
        if not isinstance(raw_edge, dict):
            raise EngineeringValidationError("Jede Verbindung muss ein Objekt sein.")
        edge_id = _text(raw_edge.get("id"), "edge.id")
        source_port = _text(raw_edge.get("sourcePort"), "edge.sourcePort")
        target_port = _text(raw_edge.get("targetPort"), "edge.targetPort")
        source_interface = interface_by_port.get(source_port)
        target_interface = interface_by_port.get(target_port)
        if source_interface is None or target_interface is None:
            raise EngineeringValidationError(
                f"Verbindung {edge_id!r} referenziert einen unbekannten Port."
            )
        relation_type = str(raw_edge.get("relationType") or "CONNECTED_TO").strip()
        if relation_type not in {"CONNECTED_TO", "COMMUNICATES_WITH", "CONNECTED_VIA"}:
            raise EngineeringValidationError(
                f"Unbekannter Beziehungstyp für Netzwerkverbindung: {relation_type!r}"
            )
        relation = _find_connection(
            str(source_interface["id"]),
            str(target_interface["id"]),
            relation_type,
            topology_id,
            edge_id,
        )
        relation_attributes = {
            "origin": ORIGIN,
            "topology_id": topology_id,
            "topology_edge_id": edge_id,
            "bus": raw_edge.get("bus"),
            "name": raw_edge.get("name"),
            "description": raw_edge.get("description"),
            "direction": raw_edge.get("direction") or "BIDIRECTIONAL",
            "routing_entry_id": raw_edge.get("routingEntryId"),
            "routing_entry_ids": raw_edge.get("routingEntryIds") or [],
            "routing_metadata": raw_edge.get("routingMetadata") or {},
        }
        if relation is None:
            relation = create_relation(
                {
                    "relation_type": relation_type,
                    "source_type": "Interface",
                    "source_id": str(source_interface["id"]),
                    "target_type": "Interface",
                    "target_id": str(target_interface["id"]),
                    "attributes": relation_attributes,
                }
            )
        else:
            relation = _update_connection_if_changed(
                relation,
                relation_type=relation_type,
                source_id=str(source_interface["id"]),
                target_id=str(target_interface["id"]),
                attributes=relation_attributes,
            )
        synchronized_edges.append(
            {"topology_edge_id": edge_id, "engineering_relation_id": str(relation["id"])}
        )

    return {
        "topology_id": topology_id,
        "nodes": synchronized_nodes,
        "edges": synchronized_edges,
        "counts": {
            "hardware_nodes": len(synchronized_nodes),
            "interfaces": len(interface_by_port),
            "connections": len(synchronized_edges),
        },
    }
