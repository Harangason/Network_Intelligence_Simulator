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
    hardware_interface_ports: dict[str, list[str]] = defaultdict(list)
    for node in topology.get("nodes", []):
        if not isinstance(node, dict):
            continue
        for port in node.get("ports", []):
            if not isinstance(port, dict) or not port.get("id") or not port.get("hardwareInterfaceId"):
                continue
            hardware_interface_ports[str(port["hardwareInterfaceId"])].append(str(port["id"]))
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
        # Positions and labels deliberately do not contribute to network identity.
        digest = sha256("\n".join(sorted(component)).encode()).hexdigest()[:12]
        network_id = f"network-{ports[port][1]}-{digest}"
        result.update({member: network_id for member in component})
    return result
