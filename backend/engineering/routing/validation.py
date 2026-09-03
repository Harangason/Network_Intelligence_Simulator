"""Technical consistency checks for routing entries and routing tables."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from ..db import get_connection
from ..project_context import current_project_id

PROTOCOL_CAPACITY = {
    "CAN": (500_000, 8),
    "CAN_FD": (2_000_000, 64),
    "CAN_XL": (10_000_000, 2048),
    "LIN": (19_200, 8),
    "FLEXRAY": (10_000_000, 254),
    "ETHERNET": (100_000_000, 65_535),
    "SOME_IP": (100_000_000, 65_535),
    "TCP": (100_000_000, 65_535),
    "UDP": (100_000_000, 65_507),
    "DDS": (100_000_000, 65_535),
    "ROS_2": (100_000_000, 65_535),
    "OPC_UA": (100_000_000, 65_535),
    "ETHERCAT": (100_000_000, 1486),
    "PROFINET": (100_000_000, 1440),
    "MODBUS": (100_000, 253),
    "ARINC": (100_000, 4),
    "MIL_STD_1553": (1_000_000, 4),
    "PCIE": (8_000_000_000, 4096),
    "CUSTOM": (1_000_000, 65_535),
}

INTERFACE_PROTOCOLS = {
    "CAN": {"CAN"},
    "CAN_FD": {"CAN", "CAN_FD"},
    "LIN": {"LIN"},
    "FlexRay": {"FLEXRAY"},
    "Ethernet": {"ETHERNET", "SOME_IP", "TCP", "UDP", "DDS", "ROS_2", "OPC_UA"},
    "EtherCAT": {"ETHERCAT"},
    "ProfiNET": {"PROFINET"},
    "ModbusTCP": {"MODBUS", "TCP"},
    "ModbusRTU": {"MODBUS"},
    "OPCUA": {"OPC_UA"},
    "ARINC": {"ARINC"},
    "MIL_STD_1553": {"MIL_STD_1553"},
    "PCIe": {"PCIE"},
    "Other": set(PROTOCOL_CAPACITY),
}


def detect_routing_loop(hops: list[Any]) -> list[str]:
    identities: list[str] = []
    for hop in hops:
        if isinstance(hop, dict):
            identity = str(hop.get("node_id") or hop.get("network_id") or hop.get("id") or hop.get("name") or "")
        else:
            identity = str(hop)
        if identity:
            identities.append(identity)
    seen: set[str] = set()
    duplicates: list[str] = []
    for identity in identities:
        if identity in seen and identity not in duplicates:
            duplicates.append(identity)
        seen.add(identity)
    return duplicates


def is_gateway_fanout_interface(interface: dict[str, Any]) -> bool:
    name = str(interface.get("name") or "").strip().lower()
    parts = name.split("_")
    return len(parts) == 3 and parts[0] == "system" and all(part.isdigit() for part in parts[1:])


class RoutingValidator:
    """Validates references, path semantics, timing, payload and estimated load."""

    def __init__(self, project_id: str | None = None):
        self.project_id = project_id or current_project_id()

    def _physical_path_mapping(
        self,
        source_node_id: str,
        destination_node_ids: list[str],
    ) -> tuple[bool | None, list[str]]:
        project_id = getattr(self, "project_id", None)
        if not project_id or not source_node_id or not destination_node_ids:
            return None, []
        with get_connection() as connection:
            hardware_interfaces = connection.execute(
                "SELECT hardware_node_id, network_ref FROM engineering_hardware_interfaces "
                "WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s "
                "AND network_ref IS NOT NULL AND network_ref <> ''",
                ([source_node_id, *destination_node_ids], project_id),
            ).fetchall()
            networks_by_node: dict[str, set[str]] = {}
            for item in hardware_interfaces:
                networks_by_node.setdefault(str(item["hardware_node_id"]), set()).add(str(item["network_ref"]))
            source_networks = networks_by_node.get(source_node_id, set())
            hardware_unmapped = [
                destination_id
                for destination_id in destination_node_ids
                if not source_networks.intersection(networks_by_node.get(destination_id, set()))
            ]
            if source_networks and not hardware_unmapped:
                return True, []
            row = connection.execute(
                "SELECT topology FROM engineering_workflow_projects WHERE project_id = %s",
                (project_id,),
            ).fetchone()
        topology = row.get("topology") if row else None
        if not isinstance(topology, dict):
            return False, destination_node_ids
        nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
        edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
        engineering_to_topology = {
            str(node.get("engineeringId") or node.get("engineering_id")): str(node.get("id"))
            for node in nodes
            if isinstance(node, dict)
            and node.get("id")
            and (node.get("engineeringId") or node.get("engineering_id"))
        }
        source_topology_id = engineering_to_topology.get(source_node_id)
        if not source_topology_id:
            return False, destination_node_ids
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source and target:
                adjacency.setdefault(source, set()).add(target)
                adjacency.setdefault(target, set()).add(source)

        reachable = {source_topology_id}
        frontier = [source_topology_id]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    frontier.append(neighbor)
        unmapped = [
            destination_id
            for destination_id in destination_node_ids
            if engineering_to_topology.get(destination_id) not in reachable
        ]
        return not unmapped, unmapped

    def _rows(self, table: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE id = ANY(%s::uuid[]) AND project_id = %s",
                (ids, self.project_id),
            ).fetchall()
        return {str(row["id"]): row for row in rows}

    def _find_duplicates(
        self,
        source_node_id: str,
        payload: dict[str, Any],
        destinations: list[dict[str, Any]],
        exclude_route_id: str | None,
    ) -> list[dict[str, Any]]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, route_code FROM engineering_routing_entries "
                "WHERE source ->> 'node_id' = %s AND payload = %s AND destinations = %s "
                "AND (%s::uuid IS NULL OR id <> %s::uuid) "
                "AND status NOT IN ('REJECTED', 'SUPERSEDED', 'OUTDATED') "
                "AND project_id = %s",
                (
                    source_node_id,
                    Jsonb(payload),
                    Jsonb(destinations),
                    exclude_route_id,
                    exclude_route_id,
                    self.project_id,
                ),
            ).fetchall()

    def validate(self, route: dict[str, Any], *, exclude_route_id: str | None = None) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        evidence: list[dict[str, Any]] = []

        def error(code: str, message: str) -> None:
            errors.append({"code": code, "message": message})

        def warn(code: str, message: str) -> None:
            warnings.append({"code": code, "message": message})

        source = route.get("source") or {}
        destinations = route.get("destinations") or []
        payload = route.get("payload") or {}
        path = route.get("route") or {}
        timing = route.get("timing") or {}
        policy = route.get("routing_policy") or {}

        source_node_id = str(source.get("node_id") or "")
        destination_node_ids = [str(item.get("node_id") or "") for item in destinations if isinstance(item, dict)]
        node_ids = [item for item in [source_node_id, *destination_node_ids] if item]
        nodes = self._rows("engineering_hardware_nodes", node_ids)
        if source_node_id not in nodes:
            error("SOURCE_NOT_FOUND", "Der Source Hardware Node existiert nicht.")
        for node_id in destination_node_ids:
            if node_id not in nodes:
                error("DESTINATION_NOT_FOUND", f"Destination {node_id} existiert nicht.")
            if node_id == source_node_id:
                error("SOURCE_EQUALS_DESTINATION", "Source und Destination dürfen nicht identisch sein.")

        physical_path_mapped, unmapped_destinations = self._physical_path_mapping(
            source_node_id,
            destination_node_ids,
        )
        if physical_path_mapped is False:
            warn(
                "UNMAPPED_ROUTE",
                "Für diese Route existiert im Netzwerk-Editor noch kein physischer Pfad.",
            )

        interface_ids = [str(source.get("interface_id") or "")]
        interface_ids.extend(str(item.get("interface_id") or "") for item in destinations if isinstance(item, dict))
        interface_ids = [item for item in interface_ids if item]
        interfaces = self._rows("engineering_interfaces", interface_ids)
        source_interface_id = str(source.get("interface_id") or "")
        if source_interface_id:
            source_interface = interfaces.get(source_interface_id)
            if source_interface is None:
                error("SOURCE_INTERFACE_NOT_FOUND", "Das Source Interface existiert nicht.")
            elif source_interface.get("hardware_node_id") and str(source_interface["hardware_node_id"]) != source_node_id:
                error("SOURCE_INTERFACE_MISMATCH", "Das Source Interface gehört nicht zum Source Node.")
        else:
            warn("SOURCE_INTERFACE_MISSING", "Kein Source Interface ausgewählt.")

        for destination in destinations:
            interface_id = str(destination.get("interface_id") or "")
            if not interface_id:
                warn("DESTINATION_INTERFACE_MISSING", f"Für {destination.get('node_id')} ist kein Ziel-Interface gesetzt.")
                continue
            interface = interfaces.get(interface_id)
            if interface is None:
                error("DESTINATION_INTERFACE_NOT_FOUND", f"Destination Interface {interface_id} existiert nicht.")
            elif interface.get("hardware_node_id") and str(interface["hardware_node_id"]) != str(destination.get("node_id")):
                error("DESTINATION_INTERFACE_MISMATCH", "Ein Destination Interface gehört nicht zum gewählten Node.")

        raw_hardware_interface_ids = [str(source.get("port_id") or "")]
        raw_hardware_interface_ids.extend(str(item.get("port_id") or "") for item in destinations if isinstance(item, dict))
        hardware_interface_ids = []
        for item in raw_hardware_interface_ids:
            try:
                hardware_interface_ids.append(str(UUID(item)))
            except (ValueError, TypeError, AttributeError):
                # A synchronized topology uses stable port names instead of
                # canonical HardwareNetworkInterface UUIDs.
                continue
        hardware_interfaces = self._rows("engineering_hardware_interfaces", hardware_interface_ids)
        source_port_id = str(source.get("port_id") or "")
        if source_port_id in hardware_interface_ids:
            source_port = hardware_interfaces.get(source_port_id)
            if source_port is None:
                error("SOURCE_HARDWARE_INTERFACE_NOT_FOUND", "Das physische Source Hardware Interface existiert nicht.")
            elif str(source_port.get("hardware_node_id") or "") != source_node_id:
                error("SOURCE_HARDWARE_INTERFACE_MISMATCH", "Das physische Source Interface gehört nicht zum Source Node.")
        for destination in destinations:
            port_id = str(destination.get("port_id") or "")
            if port_id not in hardware_interface_ids:
                continue
            port = hardware_interfaces.get(port_id)
            if port is None:
                error("DESTINATION_HARDWARE_INTERFACE_NOT_FOUND", f"Hardware Interface {port_id} existiert nicht.")
            elif str(port.get("hardware_node_id") or "") != str(destination.get("node_id") or ""):
                error("DESTINATION_HARDWARE_INTERFACE_MISMATCH", "Ein physisches Destination Interface gehört nicht zum gewählten Node.")

        message_ids = list(dict.fromkeys([
            *[str(item) for item in payload.get("message_ids", []) if item],
            *([str(payload.get("message_id"))] if payload.get("message_id") else []),
        ]))
        messages = self._rows("engineering_messages", message_ids)
        for message_id in message_ids:
            if message_id not in messages:
                error("MESSAGE_NOT_FOUND", f"Die referenzierte Message {message_id} existiert nicht.")
        message = messages.get(message_ids[0]) if message_ids else None

        signal_ids = [str(item) for item in payload.get("signal_ids", []) if item]
        signals = self._rows("engineering_signals", signal_ids)
        for signal_id in signal_ids:
            signal = signals.get(signal_id)
            if signal is None:
                error("SIGNAL_NOT_FOUND", f"Signal {signal_id} existiert nicht.")
            elif message_ids and str(signal.get("message_id") or "") not in message_ids:
                error("SIGNAL_MESSAGE_MISMATCH", f"Signal {signal.get('name')} gehört zu keiner gewählten Message.")
        if not message_ids and not signal_ids and not payload.get("topic") and not payload.get("data_object"):
            warn("PAYLOAD_UNSPECIFIED", "Die Route hat noch keinen konkreten Payload.")

        protocol = str(source.get("protocol") or "CUSTOM").upper()
        if protocol not in PROTOCOL_CAPACITY:
            warn("CUSTOM_PROTOCOL", f"Für das Protokoll {protocol} liegen keine Standardkapazitäten vor.")
            protocol = "CUSTOM"
        shared_network_transport = bool(source.get("network_id")) and all(
            destination.get("network_id") == source.get("network_id")
            for destination in destinations
            if isinstance(destination, dict)
        )
        protocol_interfaces = hardware_interfaces.values() if hardware_interface_ids \
            else [] if shared_network_transport \
            else interfaces.values()
        for interface in protocol_interfaces:
            if is_gateway_fanout_interface(interface):
                error(
                    "GATEWAY_FANOUT_INTERFACE",
                    f"Interface {interface.get('name')} ist ein Systemgateway-Fanout-Duplikat und darf nicht als Routing-Endpunkt verwendet werden.",
                )
            interface_type = str(interface.get("technology") or interface.get("interface_type") or "Other")
            supported = INTERFACE_PROTOCOLS.get(interface_type, set(PROTOCOL_CAPACITY))
            if protocol not in supported and not path.get("transformations"):
                error(
                    "PROTOCOL_INCOMPATIBLE",
                    f"Interface {interface.get('name')} unterstützt {protocol} nicht; eine Transformation fehlt.",
                )

        loop_nodes = detect_routing_loop(path.get("hops", []))
        if loop_nodes:
            error("ROUTING_LOOP", f"Routing loop detected: {', '.join(loop_nodes)}.")

        gateways = [str(item.get("node_id") if isinstance(item, dict) else item) for item in path.get("gateways", [])]
        gateway_rows = self._rows("engineering_hardware_nodes", [item for item in gateways if item])
        for gateway_id in gateways:
            gateway = gateway_rows.get(gateway_id)
            if gateway is None:
                error("GATEWAY_NOT_FOUND", f"Gateway {gateway_id} existiert nicht.")
            elif gateway.get("device_type") != "Gateway":
                error("INVALID_GATEWAY", f"{gateway.get('name')} ist nicht als Gateway klassifiziert.")

        if policy.get("routing_type") == "MULTICAST" and len(destinations) < 2:
            warn("MULTICAST_SINGLE_TARGET", "MULTICAST hat nur einen Consumer.")
        if policy.get("routing_type") == "UNICAST" and len(destinations) > 1:
            error("UNICAST_MULTIPLE_TARGETS", "UNICAST darf nur eine Destination enthalten.")
        if policy.get("routing_type") == "CONDITIONAL" and not policy.get("conditions"):
            error("CONDITION_MISSING", "CONDITIONAL Routing benötigt mindestens eine Bedingung.")
        if policy.get("redundancy") not in (None, "NONE") and not policy.get("fallback_route_id"):
            warn("FALLBACK_MISSING", "Redundantes Routing besitzt keine Fallback-Route.")

        payload_bits = 0
        frame_payload_bytes = 0
        if signals:
            payload_bits = sum(int(signal.get("length_bits") or 0) for signal in signals.values())
            bits_by_message: dict[str, int] = {}
            for signal in signals.values():
                key = str(signal.get("message_id") or "unassigned")
                bits_by_message[key] = bits_by_message.get(key, 0) + int(signal.get("length_bits") or 0)
            frame_payload_bytes = max((ceil(bits / 8) for bits in bits_by_message.values()), default=0)
        elif messages:
            message_payloads = [int(item.get("dlc") or 0) for item in messages.values()]
            payload_bits = sum(message_payloads) * 8
            frame_payload_bytes = max(message_payloads, default=0)
        payload_bytes = ceil(payload_bits / 8) if payload_bits else 0
        bitrate, max_payload = PROTOCOL_CAPACITY[protocol]
        if frame_payload_bytes > max_payload:
            error("PAYLOAD_TOO_LARGE", f"Payload {frame_payload_bytes} Byte überschreitet {max_payload} Byte für {protocol}.")

        hop_count = max(1, len(path.get("hops", [])) - 1)
        gateway_count = len(gateways)
        estimated_latency_ms = round(0.2 + hop_count * 0.35 + gateway_count * 0.8, 3)
        max_latency = timing.get("max_latency_ms")
        if max_latency and estimated_latency_ms > float(max_latency):
            error(
                "LATENCY_UNACHIEVABLE",
                f"Geschätzte Latenz {estimated_latency_ms} ms überschreitet {max_latency} ms.",
            )
        jitter = timing.get("jitter_limit_ms")
        if jitter and float(jitter) < gateway_count * 0.1:
            warn("JITTER_TIGHT", "Das Jitter-Limit ist für die Gateway-Anzahl sehr knapp.")

        message_cycles = [float(item.get("cycle_ms")) for item in messages.values() if item.get("cycle_ms")]
        message_cycle_ms = min(message_cycles) if message_cycles else None
        cycle_ms = float(timing.get("cycle_time_ms") or message_cycle_ms or 100.0)
        cycle_ms = cycle_ms or 100.0
        route_load = (payload_bits / (cycle_ms / 1000.0) / bitrate * 100) if payload_bits else 0.0
        segment_ids = {
            str(item.get("network_id") or "").strip()
            for item in [source, path, *[destination for destination in destinations if isinstance(destination, dict)]]
            if str(item.get("network_id") or "").strip()
        }
        segment_count = len(segment_ids) or 1
        expected_load = min(100.0, route_load * segment_count)
        if expected_load > 90:
            error("BUS_LOAD_CRITICAL", f"Erwartete zusätzliche Buslast {expected_load:.1f} % ist kritisch.")
        elif expected_load > 75:
            warn("BUS_LOAD_HIGH", f"Erwartete zusätzliche Buslast {expected_load:.1f} % ist hoch.")

        if source_node_id and destination_node_ids:
            duplicates = self._find_duplicates(
                source_node_id, payload, destinations, exclude_route_id
            )
            if duplicates:
                error("DUPLICATE_ROUTE", f"Eine identische Route existiert bereits ({duplicates[0]['route_code']}).")

        evidence.extend(
            [
                {"type": "TOPOLOGY", "source_node": source_node_id, "destinations": destination_node_ids},
                {"type": "PROTOCOL", "protocol": protocol, "compatible": not any(item["code"] == "PROTOCOL_INCOMPATIBLE" for item in errors)},
                {"type": "TIMING", "estimated_latency_ms": estimated_latency_ms, "max_latency_ms": max_latency},
                {
                    "type": "LOAD",
                    "payload_bytes": payload_bytes,
                    "route_load_percent": round(expected_load, 3),
                    "physical_segment_count": segment_count,
                },
                {
                    "type": "PHYSICAL_NETWORK",
                    "mapped": physical_path_mapped,
                    "unmapped_destinations": unmapped_destinations,
                },
            ]
        )
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "validation_timestamp": datetime.now(UTC).isoformat(),
            "metrics": {
                "payload_bytes": payload_bytes,
                "estimated_latency_ms": estimated_latency_ms,
                "route_load_percent": round(expected_load, 3),
                "physical_segment_count": segment_count,
                "hop_count": hop_count,
                "gateway_count": gateway_count,
                "physical_path_mapped": physical_path_mapped,
            },
            "evidence": evidence,
        }

    def validate_table(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        results = [self.validate(route, exclude_route_id=str(route.get("id")) if route.get("id") else None) for route in routes]
        table_errors = [] if results else [
            {
                "code": "ROUTING_TABLE_EMPTY",
                "message": "Die Routing-Tabelle enthaelt noch keine Route.",
            }
        ]
        return {
            "valid": bool(results) and all(result["valid"] for result in results),
            "route_count": len(routes),
            "valid_count": sum(1 for result in results if result["valid"]),
            "error_count": len(table_errors) + sum(len(result["errors"]) for result in results),
            "warning_count": sum(len(result["warnings"]) for result in results),
            "table_errors": table_errors,
            "results": results,
        }
