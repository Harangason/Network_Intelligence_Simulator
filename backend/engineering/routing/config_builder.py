"""Build simulator configuration from approved routing entries."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..db import get_connection
from ..project_context import current_project_id

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
    "CUSTOM": "generic",
}


class CommunicationConfigBuilder:
    def build(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        approved = [route for route in routes if route.get("approval_state") == "APPROVED"]
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
                    "SELECT id, name, device_type FROM engineering_hardware_nodes "
                    "WHERE id = ANY(%s::uuid[]) AND project_id = %s",
                    (node_ids, current_project_id()),
                ).fetchall()
            } if node_ids else {}
            interface_rows = connection.execute(
                "SELECT id, name, hardware_node_id, interface_type, configuration "
                "FROM engineering_interfaces WHERE hardware_node_id = ANY(%s::uuid[]) "
                "AND project_id = %s AND approval_state = 'approved'",
                (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
        interfaces_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for interface in interface_rows:
            configuration = interface.get("configuration") or {}
            interface_type = str(interface.get("interface_type") or "CUSTOM").upper()
            technology = PROTOCOL_TO_TECHNOLOGY.get(interface_type, "generic")
            interfaces_by_node[str(interface.get("hardware_node_id"))].append(
                {
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

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        communications = []
        for route in approved:
            protocol = str(route.get("source", {}).get("protocol") or "CUSTOM").upper()
            technology = PROTOCOL_TO_TECHNOLOGY.get(protocol, "generic")
            grouped[technology].append(route)
            for destination in route.get("destinations", []):
                communications.append(
                    {
                        "id": f"route-{route['route_code']}-{str(destination.get('node_id'))[:8]}",
                        "routing_entry_id": str(route["id"]),
                        "source": str(route["source"].get("node_id")),
                        "source_interface": route["source"].get("interface_id"),
                        "target": str(destination.get("node_id")),
                        "target_interface": destination.get("interface_id"),
                        "network_id": route["source"].get("network_id") or f"network-{technology}",
                        "technology": technology,
                        "cycle_ms": route.get("timing", {}).get("cycle_time_ms") or 100,
                        "payload_bytes": route.get("validation", {}).get("metrics", {}).get("payload_bytes") or 8,
                        "priority": route.get("route", {}).get("priority", "NORMAL"),
                        "signal_ids": route.get("payload", {}).get("signal_ids", []),
                    }
                )
        networks = [
            {
                "id": f"network-{technology}",
                "technology": technology,
                "bitrate": 2_000_000 if technology == "can_fd" else 100_000_000,
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
            for technology, grouped_routes in grouped.items()
        ]
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
