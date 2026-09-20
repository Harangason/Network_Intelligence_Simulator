"""Project a reviewed end-to-end route onto its actual physical bus segments."""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any

from ..models import EngineeringValidationError
from ..physical_segments import physical_port_networks

BUS_PROTOCOLS = {"can": "CAN", "can_fd": "CAN_FD", "can_xl": "CAN_XL", "lin": "LIN",
    "uart": "UART", "automotive_ethernet": "ETHERNET", "ethernet": "ETHERNET", "flexray": "FLEXRAY"}


class PhysicalRouteResolver:
    """Indexes for one calculation over one unchanged topology.

    Each build/capacity operation owns its resolver. Never retain it across a
    topology edit or project switch; direct single-route calls construct anew.
    """
    def __init__(self, topology: dict[str, Any] | None = None):
        self.topology = topology or {}
        self.nodes = {str(node.get("id")): node for node in self.topology.get("nodes") or [] if isinstance(node, dict)}
        self.by_hardware = {str(node.get("engineeringId") or node.get("engineering_id")): key for key, node in self.nodes.items()}
        self.route_edges = defaultdict(list)
        for edge in self.topology.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            refs = {str(item) for item in edge.get("routingEntryIds") or []}
            refs.add(str(edge.get("routingEntryId") or edge.get("routing_entry_id") or ""))
            for route_id in refs:
                self.route_edges[route_id].append(edge)
        self.port_networks = None

    def resolve(self, route: dict[str, Any], destination: dict[str, Any]) -> list[dict[str, Any]]:
        """Use route-linked edges; never relocate receivers onto the source bus."""
        nodes, by_hardware = self.nodes, self.by_hardware
        source = route.get("source") or {}
        source_node, target_node = str(source.get("node_id")), str(destination.get("node_id"))
        source_id, target_id = by_hardware.get(source_node), by_hardware.get(target_node)
        graph = defaultdict(list)
        for edge in self.route_edges.get(str(route.get("id")), []):
            left, right = str(edge.get("source")), str(edge.get("target"))
            graph[left].append((right, edge, True))
            graph[right].append((left, edge, False))
        queue = deque([(source_id, [])]) if source_id and target_id else deque()
        visited = {source_id}
        path = None
        while queue:
            current, steps = queue.popleft()
            if current == target_id:
                path = steps
                break
            for neighbor, edge, forward in sorted(graph[current], key=lambda item: str(item[1].get("id"))):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, [*steps, (current, neighbor, edge, forward)]))
        if not path:
            source_network = str(source.get("network_id") or "")
            destination_network = str(destination.get("network_id") or source_network)
            if destination_network != source_network:
                raise EngineeringValidationError(
                    f"Route {route.get('name') or route.get('id')}: Für den Übergang von {source_network} "
                    f"nach {destination_network} fehlen bestätigte physische Gateway-Segmente.")
            return [{"source": deepcopy(source), "target": {**deepcopy(destination),
                "network_id": destination_network, "protocol": destination.get("protocol") or source.get("protocol")}}]

        if self.port_networks is None:
            self.port_networks = physical_port_networks(self.topology)
        networks = self.port_networks

        def endpoint(node_id, port_id, edge):
            node = nodes[node_id]
            port = next((item for item in node.get("ports") or [] if str(item.get("id")) == str(port_id)), None)
            if not port:
                raise EngineeringValidationError(f"Route {route.get('id')}: Physischer Port {port_id} fehlt.")
            hardware = str(node.get("engineeringId") or node.get("engineering_id") or "")
            original = source if hardware == source_node else destination if hardware == target_node else {}
            hardware_interface = str(port.get("hardwareInterfaceId") or port.get("hardware_interface_id") or "")
            return {**deepcopy(original), "node_id": hardware,
                "interface_id": original.get("interface_id") or port.get("engineeringId") or hardware_interface or str(port_id),
                "hardware_interface_id": hardware_interface or None, "port_id": hardware_interface or str(port_id),
                "physical_port_ref": str(port_id),
                "network_id": networks.get(str(port_id)) or edge.get("physicalNetworkId") or original.get("network_id"),
                "network_name": edge.get("physicalNetworkName") or port.get("physicalNetworkName") or original.get("network_name"),
                "protocol": BUS_PROTOCOLS.get(str(edge.get("bus")), str(edge.get("bus") or original.get("protocol") or "CUSTOM").upper())}

        segments = []
        for left, right, edge, forward in path:
            segment = {"source": endpoint(left, edge.get("sourcePort") if forward else edge.get("targetPort"), edge),
                "target": endpoint(right, edge.get("targetPort") if forward else edge.get("sourcePort"), edge),
                "topology_edge_ids": [str(edge.get("id"))]}
            # Several linked edges on one shared bus describe a single transmission.
            if segments and segments[-1]["source"]["network_id"] == segment["source"]["network_id"]:
                segments[-1]["target"] = segment["target"]
                segments[-1]["topology_edge_ids"].extend(segment["topology_edge_ids"])
            else:
                segments.append(segment)
        return segments


def physical_route_segments(route: dict[str, Any], destination: dict[str, Any],
                            topology: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return PhysicalRouteResolver(topology).resolve(route, destination)
