"""Build simulator configuration from approved routing entries."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any

from ..db import get_connection
from ..project_context import current_project_id
from ..addressing import format_logical_node_address
from .validation import PROTOCOL_CAPACITY
from ..models import EngineeringValidationError

IP_FIELDS = ("ipv4", "ipv6", "mac", "mac_address", "ip_version", "transport_protocol", "source_port", "destination_port", "udp_port", "tcp_port", "mtu", "vlan_id")

PROTOCOL_TO_TECHNOLOGY = {
    "CAN": "can",
    "CAN_FD": "can_fd",
    "CAN_XL": "can_xl",
    "LIN": "lin",
    "FLEXRAY": "flexray",
    "ETHERNET": "automotive_ethernet",
    "SOME_IP": "someip",
    "TCP": "tcp",
    "UDP": "udp",
    "DDS": "dds",
    "ROS_2": "ros2",
    "OPC_UA": "opcua",
    "ETHERCAT": "ethercat",
    "PROFINET": "profinet",
    "MODBUS": "modbus_tcp",
    "ARINC": "arinc429",
    "MIL_STD_1553": "mil_std_1553",
    "MVB": "mvb",
    "WTB": "wtb",
    "ETB": "etb",
    "TRDP": "trdp",
    "PCIE": "pcie",
    "CUSTOM": "generic",
}


class CommunicationConfigBuilder:
    def build(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        approved = [
            route for route in routes
            if route.get("approval_state") == "APPROVED"
            and route.get("status") not in {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}
        ]
        node_ids = sorted(
            {
                str(route["source"].get("node_id"))
                for route in approved
                if route.get("source", {}).get("node_id")
            }
            | {
                str(destination.get("node_id"))
                for route in approved
                for destination in route.get("destinations", [])
                if destination.get("node_id")
            }
        )
        with get_connection() as connection:
            nodes = {
                str(row["id"]): row
                for row in connection.execute(
                    "SELECT id, name, device_type, logical_node_address, address_namespace FROM engineering_hardware_nodes "
                    "WHERE id = ANY(%s::uuid[]) AND project_id = %s",
                    (node_ids, current_project_id()),
                ).fetchall()
            } if node_ids else {}
            interface_rows = connection.execute(
                "SELECT id, name, hardware_node_id, interface_type, configuration "
                "FROM engineering_interfaces WHERE hardware_node_id = ANY(%s::uuid[]) "
                "AND project_id = %s",
                (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
            hardware_interfaces = connection.execute(
                "SELECT id, hardware_node_id, physical_port_ref, capabilities, network_ref FROM engineering_hardware_interfaces "
                "WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s",
                (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
            bindings = connection.execute(
                "SELECT * FROM engineering_technology_address_bindings WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s",
                (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
        physical = {str(row["id"]): row for row in hardware_interfaces}
        interfaces_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for interface in interface_rows:
            configuration = interface.get("configuration") or {}
            interface_type = str(interface.get("interface_type") or "CUSTOM").upper()
            technology = PROTOCOL_TO_TECHNOLOGY.get(interface_type, "generic")
            interfaces_by_node[str(interface.get("hardware_node_id"))].append(
                {
                    **{key: configuration[key] for key in IP_FIELDS if key in configuration},
                    "id": str(interface["id"]),
                    "name": str(interface.get("name") or interface["id"]),
                    "technology": technology,
                    "network": str(
                        configuration.get("network_id")
                        or configuration.get("network")
                        or f"network-{technology}"
                    ),
                }
            )

        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        communications = []
        interface_networks = defaultdict(set)
        for route in approved:
            net = str(route["source"].get("network_id") or f"network-{PROTOCOL_TO_TECHNOLOGY.get(str(route['source'].get('protocol') or 'CUSTOM').upper(), 'generic')}")
            for endpoint in [route["source"], *route.get("destinations", [])]:
                raw_id = str(endpoint.get("interface_id") or endpoint.get("port_id") or f"{endpoint.get('node_id')}-{net}")
                interface_networks[(str(endpoint.get("node_id")), raw_id)].add(net)
        for route in approved:
            protocol = str(route.get("source", {}).get("protocol") or "CUSTOM").upper()
            technology = PROTOCOL_TO_TECHNOLOGY.get(protocol, "generic")
            network_id = str(route["source"].get("network_id") or f"network-{technology}")
            grouped[(network_id, technology, protocol)].append(route)
            # The approved route owns the physical network assignment. Its
            # endpoint may be a logical or a directly connected hardware port.
            endpoints = [route["source"], *route.get("destinations", [])]
            def endpoint_id(endpoint):
                raw_id = str(endpoint.get("interface_id") or endpoint.get("port_id") or f"{endpoint.get('node_id')}-{network_id}")
                return raw_id + ":segment:" + sha256(network_id.encode()).hexdigest()[:12] if len(interface_networks[(str(endpoint.get("node_id")), raw_id)]) > 1 else raw_id
            for endpoint in endpoints:
                node_id = str(endpoint.get("node_id"))
                interface_id = endpoint_id(endpoint)
                existing = next((item for item in interfaces_by_node[node_id] if item["id"] == interface_id), None)
                if existing is None:
                    template = next((item for item in interfaces_by_node[node_id] if item["id"] == str(endpoint.get("interface_id"))), {})
                    interfaces_by_node[node_id].append({**template, "id": interface_id, "name": interface_id, "technology": technology, "network": network_id})
                else:
                    # The executable snapshot describes this concrete route
                    # segment, not every physical capability of the canonical
                    # interface. Keep technology and network atomic so an old
                    # interface capability cannot appear on the newly assigned
                    # route network (for example Ethernet on a CAN-FD segment).
                    existing["technology"] = technology
                    existing["network"] = network_id
                existing = next(item for item in interfaces_by_node[node_id] if item["id"] == interface_id)
                hw = physical.get(str(endpoint.get("hardware_interface_id") or endpoint.get("port_id") or interface_id), {})
                capabilities = hw.get("capabilities") or {}
                existing.update({key: capabilities[key] for key in IP_FIELDS if key in capabilities})
                existing.update({key: endpoint[key] for key in IP_FIELDS if key in endpoint})
                existing["physical_port_ref"] = node_id + ":" + str(endpoint.get("physical_port_ref") or hw.get("physical_port_ref") or endpoint.get("port_id") or interface_id)
                for binding in bindings:
                    if str(binding["hardware_node_id"]) != node_id or (binding.get("network_ref") and str(binding["network_ref"]) != network_id):
                        continue
                    if binding.get("hardware_interface_ref") and str(binding["hardware_interface_ref"]) not in {interface_id, str(hw.get("id") or "")}:
                        continue
                    key = {"IPV4": "ipv4", "IPV6": "ipv6", "MAC": "mac", "ETHERNET_MAC": "mac"}.get(str(binding["technology"]).upper())
                    if not key or binding["status"] == "PROPOSED":
                        continue
                    if binding["status"] != "ASSIGNED":
                        raise EngineeringValidationError(f"Adressbindung {binding['id']} ist {binding['status']}; vor der Simulation klären.")
                    value = str(binding["technology_address"])
                    previous = existing.get(key)
                    if previous and str(previous).split("/")[0].lower() != value.split("/")[0].lower():
                        raise EngineeringValidationError(f"Widersprüchliche {key}-Adressierung am Interface {interface_id}.")
                    existing[key] = value
                    existing.setdefault("address_binding_refs", []).append(str(binding["id"]))
            for destination in route.get("destinations", []):
                source_node = nodes.get(str(route["source"].get("node_id")), {})
                destination_node = nodes.get(str(destination.get("node_id")), {})
                communications.append(
                    {
                        **{key: route.get("route", {})[key] for key in IP_FIELDS if key in route.get("route", {})},
                        "id": f"route-{route['route_code']}-{str(destination.get('node_id'))[:8]}",
                        "routing_entry_id": str(route["id"]),
                        "source": str(route["source"].get("node_id")),
                        "source_name": nodes.get(str(route["source"].get("node_id")), {}).get("name"),
                        "source_logical_address": (
                            format_logical_node_address(int(source_node["logical_node_address"]))
                            if source_node.get("logical_node_address") is not None else None
                        ),
                        "source_interface": endpoint_id(route["source"]),
                        "target": str(destination.get("node_id")),
                        "target_name": nodes.get(str(destination.get("node_id")), {}).get("name"),
                        "destination_logical_address": (
                            format_logical_node_address(int(destination_node["logical_node_address"]))
                            if destination_node.get("logical_node_address") is not None else None
                        ),
                        "target_interface": endpoint_id(destination),
                        "network_id": route["source"].get("network_id") or f"network-{technology}",
                        "network_name": route["source"].get("network_name") or network_id,
                        "technology": technology,
                        "cycle_ms": route.get("timing", {}).get("cycle_time_ms") or 100,
                        "deadline_ms": route.get("timing", {}).get("deadline_ms"),
                        "payload_bytes": route.get("validation", {}).get("metrics", {}).get("payload_bytes") or 8,
                        "priority": route.get("route", {}).get("priority", "NORMAL"),
                        "signal_ids": route.get("payload", {}).get("signal_ids", []),
                    }
                )
        networks = [
            {
                "id": network_id,
                "name": next((str(route.get("source", {}).get("network_name") or "").strip()
                              for route in grouped_routes
                              if str(route.get("source", {}).get("network_name") or "").strip()), network_id),
                "technology": technology,
                "bitrate": PROTOCOL_CAPACITY.get(protocol, (100_000_000, 1500))[0],
                "cycle_ms": min(float(route.get("timing", {}).get("cycle_time_ms") or 100) for route in grouped_routes),
                "nodes": sorted(
                    {
                        str(route["source"].get("node_id"))
                        for route in grouped_routes
                    }
                    | {
                        str(destination.get("node_id"))
                        for route in grouped_routes
                        for destination in route.get("destinations", [])
                    }
                ),
            }
            for (network_id, technology, protocol), grouped_routes in grouped.items()
        ]
        used_interfaces = {item[key] for item in communications for key in ("source_interface", "target_interface")}
        # A transport snapshot contains executable ports only. Unrouted model
        # capabilities may reference networks absent from this simulation.
        for node_id in interfaces_by_node:
            interfaces_by_node[node_id] = [item for item in interfaces_by_node[node_id] if item["id"] in used_interfaces]
        return {
            "config": {
                "name": "approved_routing_table",
                "industry": "generic",
                "duration_s": 1,
                "cycle_ms": min((item["cycle_ms"] for item in networks), default=100),
                "node_count": len(nodes),
                "networks": networks,
                "hardware": {
                    "devices": [
                        {
                            "id": node_id,
                            "name": nodes.get(node_id, {}).get("name", node_id),
                            "type": nodes.get(node_id, {}).get("device_type", "GenericDevice"),
                            "logical_node_address": nodes.get(node_id, {}).get("logical_node_address"),
                            "formatted_logical_node_address": (
                                format_logical_node_address(int(nodes[node_id]["logical_node_address"]))
                                if nodes.get(node_id, {}).get("logical_node_address") is not None else None
                            ),
                            "address_namespace": nodes.get(node_id, {}).get("address_namespace") or "PROJECT",
                            "interfaces": interfaces_by_node.get(node_id, []),
                        }
                        for node_id in node_ids
                    ]
                },
                "communications": communications,
                "routing_entry_ids": [str(route["id"]) for route in approved],
                "formats": ["universal-jsonl", "universal-csv"],
            }
        }
