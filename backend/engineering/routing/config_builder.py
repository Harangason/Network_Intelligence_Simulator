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


def _timing_requirements(route: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    timing = route.get("timing") or {}
    aliases = {
        "maximum_latency_ms": ("max_latency_ms", "maximum_latency_ms", "deadline_ms"),
        "jitter_limit_ms": ("jitter_limit_ms", "maximum_jitter_ms", "jitter_ms"),
        "timeout_ms": ("timeout_ms",),
        "freshness_ms": ("freshness_ms", "data_freshness_limit"),
    }
    result, provenance = {}, {}
    for field, keys in aliases.items():
        for source_name, source in (("route", timing), ("project_parameters", parameters)):
            found = next(((key, source[key]) for key in keys if source.get(key) is not None), None)
            if found:
                result[field] = found[1]
                provenance[field] = {"source": source_name, "field": found[0], "unit": "ms"}
                if source_name == "route" and (timing.get("provenance") or {}).get(found[0]):
                    provenance[field]["origin"] = timing["provenance"][found[0]]
                break
    if "maximum_latency_ms" in result:
        result["deadline_ms"] = result["maximum_latency_ms"]
    return {**result, "requirement_provenance": provenance}


class CommunicationConfigBuilder:
    def build(self, routes: list[dict[str, Any]], *, topology: dict[str, Any] | None = None,
              parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        from .transport_segments import physical_route_segments
        from ..capacity.service import parameters_for_protocol

        parameters = parameters or {}
        approved = [route for route in routes if route.get("approval_state") == "APPROVED"
            and route.get("status") not in {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}]
        if approved:
            from .payload_scope import load_payload_context, payload_scope_issues
            messages, signals, logical_interfaces = load_payload_context()
            for route in approved:
                issues = payload_scope_issues(route, messages, signals, logical_interfaces)
                if issues:
                    raise EngineeringValidationError(issues[0]["message"])
        plans = [(route, destination, physical_route_segments(route, destination, topology))
            for route in approved for destination in route.get("destinations") or []]
        node_ids = sorted({str(segment[side]["node_id"]) for _, _, segments in plans
            for segment in segments for side in ("source", "target")})
        with get_connection() as connection:
            nodes = {str(row["id"]): row for row in connection.execute(
                "SELECT id, name, device_type, logical_node_address, address_namespace FROM engineering_hardware_nodes "
                "WHERE id = ANY(%s::uuid[]) AND project_id = %s", (node_ids, current_project_id()),
            ).fetchall()} if node_ids else {}
            interface_rows = connection.execute(
                "SELECT id, name, hardware_node_id, interface_type, configuration FROM engineering_interfaces "
                "WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s", (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
            hardware_interfaces = connection.execute(
                "SELECT id, hardware_node_id, physical_port_ref, capabilities, network_ref FROM engineering_hardware_interfaces "
                "WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s", (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
            bindings = connection.execute(
                "SELECT * FROM engineering_technology_address_bindings WHERE hardware_node_id = ANY(%s::uuid[]) AND project_id = %s",
                (node_ids, current_project_id()),
            ).fetchall() if node_ids else []
        physical = {str(row["id"]): row for row in hardware_interfaces}
        logical = {str(row["id"]): row for row in interface_rows}
        interfaces_by_node = defaultdict(dict)
        interface_networks = defaultdict(set)
        networks = {}
        communications = []

        def network_info(endpoint, fallback=None):
            protocol = str(endpoint.get("protocol") or (fallback or {}).get("protocol") or "CUSTOM").upper()
            technology = PROTOCOL_TO_TECHNOLOGY.get(protocol, "generic")
            network_id = str(endpoint.get("network_id") or (fallback or {}).get("network_id") or f"network-{technology}")
            return network_id, protocol, technology

        def raw_interface_id(endpoint, network_id):
            return str(endpoint.get("interface_id") or endpoint.get("port_id") or f"{endpoint.get('node_id')}-{network_id}")

        for _, _, segments in plans:
            for segment in segments:
                net, _, _ = network_info(segment["source"])
                for endpoint in (segment["source"], segment["target"]):
                    interface_networks[(str(endpoint["node_id"]), raw_interface_id(endpoint, net))].add(net)

        def bind_endpoint(endpoint, network_id, technology):
            node_id = str(endpoint["node_id"])
            raw_id = raw_interface_id(endpoint, network_id)
            interface_id = raw_id + ":segment:" + sha256(network_id.encode()).hexdigest()[:12] if len(interface_networks[(node_id, raw_id)]) > 1 else raw_id
            template = logical.get(raw_id, {})
            configuration = template.get("configuration") or {}
            hardware_id = str(endpoint.get("hardware_interface_id") or endpoint.get("port_id") or raw_id)
            hw = physical.get(hardware_id, {})
            capabilities = hw.get("capabilities") or {}
            interface = {**{key: configuration[key] for key in IP_FIELDS if key in configuration},
                "id": interface_id, "name": template.get("name") or raw_id, "technology": technology, "network": network_id,
                **{key: capabilities[key] for key in IP_FIELDS if key in capabilities},
                **{key: endpoint[key] for key in IP_FIELDS if key in endpoint},
                "physical_port_ref": node_id + ":" + str(endpoint.get("physical_port_ref") or hw.get("physical_port_ref") or endpoint.get("port_id") or raw_id)}
            for binding in bindings:
                if str(binding["hardware_node_id"]) != node_id or (binding.get("network_ref") and str(binding["network_ref"]) != network_id):
                    continue
                if binding.get("hardware_interface_ref") and str(binding["hardware_interface_ref"]) not in {raw_id, hardware_id}:
                    continue
                key = {"IPV4": "ipv4", "IPV6": "ipv6", "MAC": "mac", "ETHERNET_MAC": "mac"}.get(str(binding["technology"]).upper())
                if not key or binding["status"] == "PROPOSED":
                    continue
                if binding["status"] != "ASSIGNED":
                    raise EngineeringValidationError(f"Adressbindung {binding['id']} ist {binding['status']}; vor der Simulation klären.")
                value = str(binding["technology_address"])
                previous = interface.get(key)
                if previous and str(previous).split("/")[0].lower() != value.split("/")[0].lower():
                    raise EngineeringValidationError(f"Widersprüchliche {key}-Adressierung am Interface {interface_id}.")
                interface[key] = value
                interface.setdefault("address_binding_refs", []).append(str(binding["id"]))
            interfaces_by_node[node_id][interface_id] = interface
            return interface_id, {**configuration, **capabilities}

        def address(node_id):
            value = nodes.get(str(node_id), {}).get("logical_node_address")
            return format_logical_node_address(int(value)) if value is not None else None

        for route, destination, path in plans:
            communication_id = f"route-{route['route_code']}-{str(destination.get('node_id'))[:8]}"
            cycle_ms = (route.get("timing") or {}).get("cycle_time_ms") or parameters.get("cycle_ms") or 100
            segments = []
            for index, segment in enumerate(path):
                source, target = segment["source"], segment["target"]
                net, protocol, technology = network_info(source)
                source_interface, configuration = bind_endpoint(source, net, technology)
                target_interface, _ = bind_endpoint(target, net, technology)
                resolved = parameters_for_protocol(protocol, parameters, configuration, net)
                network = networks.setdefault(net, {"id": net, "name": source.get("network_name") or net,
                    "technology": technology, "protocol": protocol,
                    "bitrate": resolved.get("bitrate", PROTOCOL_CAPACITY.get(protocol, (100_000_000, 1500))[0]),
                    **{key: resolved[key] for key in ("arbitration_bitrate", "data_bitrate") if key in resolved},
                    "cycle_ms": cycle_ms, "nodes": set()})
                if network["technology"] != technology:
                    raise EngineeringValidationError(f"Physisches Netz {net} besitzt widersprüchliche Technologien.")
                network["nodes"].update((str(source["node_id"]), str(target["node_id"])))
                network["cycle_ms"] = min(float(network["cycle_ms"]), float(cycle_ms))
                segments.append({"id": f"{communication_id}:segment:{index}", "segment_index": index, "segment_count": len(path),
                    "source": str(source["node_id"]), "source_interface": source_interface,
                    "target": str(target["node_id"]), "target_interface": target_interface,
                    "network_id": net, "network_name": network["name"], "technology": technology,
                    "topology_edge_ids": segment.get("topology_edge_ids") or [],
                    "gateway_ids": [str(source["node_id"])] if index else []})
            first, last = segments[0], segments[-1]
            payload = route.get("payload") or {}
            message_ids = list(dict.fromkeys([*[str(item) for item in payload.get("message_ids") or []],
                *([str(payload["message_id"])] if payload.get("message_id") else [])]))
            communications.append({
                **{key: route.get("route", {})[key] for key in IP_FIELDS if key in route.get("route", {})},
                "id": communication_id, "name": route.get("name") or communication_id,
                "routing_entry_id": str(route["id"]), "routing_entry_ids": [str(route["id"])],
                "canonical_route_id": str(route["id"]),
                "source": first["source"], "source_name": nodes.get(first["source"], {}).get("name"),
                "source_interface": first["source_interface"], "source_logical_address": address(first["source"]),
                "target": last["target"], "target_name": nodes.get(last["target"], {}).get("name"),
                "target_interface": last["target_interface"], "destination_logical_address": address(last["target"]),
                "network_id": first["network_id"], "network_name": first["network_name"], "technology": first["technology"],
                "physical_network_ids": list(dict.fromkeys(item["network_id"] for item in segments)),
                "segments": segments, "cycle_ms": cycle_ms, **_timing_requirements(route, parameters),
                "payload_bytes": (route.get("validation") or {}).get("metrics", {}).get("payload_bytes", payload.get("payload_bytes", 8)),
                "priority": (route.get("route") or {}).get("priority", "NORMAL"),
                "signal_ids": payload.get("signal_ids") or [], "message_ids": message_ids,
            })
        network_rows = [{**item, "nodes": sorted(item["nodes"])} for item in networks.values()]
        return {"config": {"name": "approved_routing_table", "industry": "generic", "duration_s": 1,
            "cycle_ms": min((item["cycle_ms"] for item in network_rows), default=100), "node_count": len(nodes),
            "networks": network_rows, "parameters": parameters,
            "hardware": {"devices": [{"id": node_id, "name": nodes.get(node_id, {}).get("name", node_id),
                "type": nodes.get(node_id, {}).get("device_type", "GenericDevice"),
                "logical_node_address": nodes.get(node_id, {}).get("logical_node_address"),
                "formatted_logical_node_address": address(node_id),
                "address_namespace": nodes.get(node_id, {}).get("address_namespace") or "PROJECT",
                "interfaces": list(interfaces_by_node[node_id].values())} for node_id in node_ids]},
            "communications": communications, "routing_entry_ids": [str(route["id"]) for route in approved],
            "formats": ["universal-jsonl", "universal-csv"]}}
