"""Physical network identity is connectivity between ports, never device identity."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any


def physical_port_networks(topology: dict[str, Any]) -> dict[str, str]:
    ports = {
        str(port["id"]): (str(node["id"]), str(port.get("bus") or ""))
        for node in topology.get("nodes", []) if isinstance(node, dict) and node.get("id")
        for port in node.get("ports", []) if isinstance(port, dict) and port.get("id")
    }
    adjacency: dict[str, set[str]] = defaultdict(set)
    hardware_interface_ports: dict[tuple[str, str], list[str]] = defaultdict(list)
    explicit_network_ports: dict[tuple[str, str], set[str]] = defaultdict(set)
    explicit_network_by_port: dict[str, str] = {}
    for node in topology.get("nodes", []):
        if not isinstance(node, dict):
            continue
        for port in node.get("ports", []):
            if not isinstance(port, dict) or not port.get("id") or not port.get("hardwareInterfaceId"):
                continue
            physical_network_id = str(port.get("physicalNetworkId") or "")
            hardware_interface_ports[(str(port["hardwareInterfaceId"]), physical_network_id)].append(str(port["id"]))
            if physical_network_id:
                explicit_network_ports[(str(port.get("bus") or ""), physical_network_id)].add(str(port["id"]))
                explicit_network_by_port[str(port["id"])] = physical_network_id
    for aliases in hardware_interface_ports.values():
        if len(aliases) < 2:
            continue
        anchor = aliases[0]
        for alias in aliases[1:]:
            adjacency[anchor].add(alias)
            adjacency[alias].add(anchor)
    for edge in topology.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source, target = str(edge.get("sourcePort") or ""), str(edge.get("targetPort") or "")
        bus = str(edge.get("bus") or "")
        if ports.get(source) != (str(edge.get("source")), bus) or ports.get(target) != (str(edge.get("target")), bus):
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
        physical_network_id = str(edge.get("physicalNetworkId") or "")
        if physical_network_id:
            explicit_network_ports[(bus, physical_network_id)].update((source, target))
            explicit_network_by_port[source] = physical_network_id
            explicit_network_by_port[target] = physical_network_id
    # A shared bus is a multi-drop physical network. Its members need not form
    # artificial point-to-point edges merely to receive one network identity.
    for aliases in explicit_network_ports.values():
        ordered = sorted(aliases)
        if len(ordered) < 2:
            continue
        anchor = ordered[0]
        for alias in ordered[1:]:
            adjacency[anchor].add(alias)
            adjacency[alias].add(anchor)
    result: dict[str, str] = {}
    for port in sorted(ports):
        if port in result:
            continue
        pending, component = [port], set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        explicit_ids = {explicit_network_by_port[item] for item in component if explicit_network_by_port.get(item)}
        # Positions and labels deliberately do not contribute to network identity.
        # A single explicit bus identity is stable across route and layout changes.
        if len(explicit_ids) == 1:
            network_id = next(iter(explicit_ids))
        else:
            digest = sha256("\n".join(sorted(component)).encode()).hexdigest()[:12]
            network_id = f"network-{ports[port][1]}-{digest}"
        result.update({member: network_id for member in component})
    return result
