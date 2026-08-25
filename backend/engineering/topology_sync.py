"""Synchronize the visual network editor with the canonical engineering model."""

from __future__ import annotations

import threading
from typing import Any

from .db import get_connection
from .models import EngineeringValidationError
from .relations import create_relation
from .repository import NotFoundError, create_object, get_object, update_object

NODE_KIND_TO_DEVICE_TYPE = {
    "ecu": "ECU",
    "gateway": "Gateway",
    "sensor": "SensorController",
    "actuator": "ActuatorController",
}

BUS_TO_INTERFACE_TYPE = {
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
            "AND identity ->> 'topology_node_id' = %s",
            (topology_id, node_id),
        ).fetchone()


def _find_function(topology_id: str, hardware_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_functions "
            "WHERE hardware_node_id = %s "
            "ORDER BY CASE WHEN provenance ->> 'origin' = %s "
            "AND provenance ->> 'topology_id' = %s THEN 0 ELSE 1 END, created_at LIMIT 1",
            (hardware_id, ORIGIN, topology_id),
        ).fetchone()


def _find_interface(topology_id: str, port_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_interfaces "
            "WHERE configuration ->> 'topology_id' = %s "
            "AND configuration ->> 'topology_port_id' = %s",
            (topology_id, port_id),
        ).fetchone()


def _find_connection(source_id: str, target_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM engineering_relations "
            "WHERE relation_type = 'CONNECTED_TO' "
            "AND source_type = 'Interface' AND source_id = %s "
            "AND target_type = 'Interface' AND target_id = %s",
            (source_id, target_id),
        ).fetchone()


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
    with _sync_lock(topology_id):
        return _sync_topology(data, topology_id)


def _sync_topology(data: dict[str, Any], topology_id: str) -> dict[str, Any]:
    nodes = data.get("nodes")
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise EngineeringValidationError("'nodes' und 'edges' müssen Listen sein.")

    node_ids: set[str] = set()
    port_ids: set[str] = set()
    interface_by_port: dict[str, dict[str, Any]] = {}
    synchronized_nodes: list[dict[str, Any]] = []

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
            hardware_updates = {"name": name, "identity": identity}
            if (hardware.get("provenance") or {}).get("origin") == ORIGIN:
                hardware_updates["device_type"] = device_type
            hardware = _update_if_changed(
                "HardwareNode",
                hardware,
                hardware_updates,
            )

        function = _find_function(topology_id, str(hardware["id"]))
        function_name = f"{name} Kommunikation"
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
            port_name = _text(raw_port.get("name") or interface_type, "port.name")
            configuration = {
                "topology_id": topology_id,
                "topology_node_id": node_id,
                "topology_port_id": port_id,
                "bus": bus,
            }
            interface = _find_interface(topology_id, port_id)
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
            else:
                interface = _update_if_changed("Interface", interface, expected_interface)
            interface_by_port[port_id] = interface
            synchronized_ports.append(
                {"topology_port_id": port_id, "engineering_id": str(interface["id"])}
            )

        synchronized_nodes.append(
            {
                "topology_node_id": node_id,
                "engineering_id": str(hardware["id"]),
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
        relation = _find_connection(
            str(source_interface["id"]), str(target_interface["id"])
        )
        if relation is None:
            relation = create_relation(
                {
                    "relation_type": "CONNECTED_TO",
                    "source_type": "Interface",
                    "source_id": str(source_interface["id"]),
                    "target_type": "Interface",
                    "target_id": str(target_interface["id"]),
                    "attributes": {
                        "origin": ORIGIN,
                        "topology_id": topology_id,
                        "topology_edge_id": edge_id,
                        "bus": raw_edge.get("bus"),
                    },
                }
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
