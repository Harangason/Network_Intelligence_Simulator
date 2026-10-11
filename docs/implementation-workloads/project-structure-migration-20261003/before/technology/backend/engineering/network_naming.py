"""Rename physical bus labels without changing network or channel identity."""
from copy import deepcopy
import hashlib
import json

from .network_scene import model_signature


def rename_network(state, network_id, name, *, channels=None, name_source="user"):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError("Ein Busname mit 1 bis 120 Zeichen ohne Zeilenumbrüche ist erforderlich.")
    name = name.strip()
    parameters, topology = deepcopy(state["parameters"]), deepcopy(state["topology"])
    network = next((n for n in parameters.get("networks", []) if n.get("id") == network_id), None)
    if network is None:
        raise ValueError("Der physische Bus ist in diesem Projekt nicht mehr vorhanden.")
    previous_name = network.get("name") or network_id
    # Names are not identity. Only exact legacy defaults or an explicit binding
    # inherit a bus name; custom channel names remain independent.
    groups = {}
    for node in topology.get("nodes", []):
        for port in node.get("ports", []):
            key = port.get("hardwareInterfaceId") or port["id"]
            groups.setdefault(key, []).append((node, port))
    inherited = {}
    for key, anchors in groups.items():
        if not any(p.get("physicalNetworkId") == network_id for _, p in anchors):
            continue
        if any(p.get("physicalNetworkId") != network_id for _, p in anchors):
            raise ValueError("Ein physischer Anschluss ist mehreren Netzen zugeordnet. Bitte die Zuordnung korrigieren.")
        canonical = (channels or {}).get(key) or {}
        capabilities = canonical.get("capabilities") or {}
        if canonical and (str(canonical.get("network_ref")) != network_id or
                          any(str(n.get("engineeringId")) != str(canonical.get("hardware_node_id")) for n, _ in anchors)):
            raise ValueError("Die gespeicherte Anschlusszuordnung passt nicht zum physischen Netz.")
        explicit = capabilities.get("name_source") == "user" or any(p.get("nameSource") == "user" for _, p in anchors)
        old_names = {network_id, previous_name}
        old_names.update(p.get("physicalNetworkName") for _, p in anchors)
        old_names.discard(None)
        follows = not explicit and all(
            p.get("nameSource") == "network" or p.get("name") in old_names for _, p in anchors)
        if canonical and capabilities.get("name_source") != "network" and canonical.get("name") not in old_names:
            follows = False
        for _, port in anchors:
            if follows:
                port.update(name=name, nameSource="network")
                inherited[port["id"]] = name
            elif port.get("nameSource") == "network" or explicit:
                port["nameSource"] = "user"
            port.update(physicalNetworkName=name, physicalNetworkNameSource=name_source)
    network.update(name=name, name_source=name_source)
    for edge in topology.get("edges", []):
        if edge.get("physicalNetworkId") == network_id:
            edge.update(physicalNetworkName=name, physicalNetworkNameSource=name_source)
        for side in ("source", "target"):
            if edge.get(side + "Port") in inherited:
                edge[side + "InterfaceName"] = inherited[edge[side + "Port"]]
    scene = topology.get("scene")
    if scene:
        for bus in scene.get("buses", []):
            if bus["id"] == network_id:
                bus.update(name=name, labelText=name, nameSource=name_source)
        scene["modelSignature"] = model_signature(topology)
        scene.pop("revision", None)
        scene["revision"] = hashlib.sha256(json.dumps(scene, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return parameters, topology


def rename_network_with_interfaces(state, network_id, name, *, name_source="user"):
    """Persist canonical channel names within the caller's workflow transaction."""
    from .repository import get_object, update_object
    ports = [p for n in state["topology"].get("nodes", []) for p in n.get("ports", [])]
    channel_ids = {p["hardwareInterfaceId"] for p in ports
                   if p.get("physicalNetworkId") == network_id and p.get("hardwareInterfaceId")}
    channels = {key: get_object("HardwareNetworkInterface", key) for key in channel_ids}
    parameters, topology = rename_network(state, network_id, name, channels=channels, name_source=name_source)
    desired = {p["hardwareInterfaceId"]: p["name"] for n in topology.get("nodes", []) for p in n.get("ports", [])
               if p.get("physicalNetworkId") == network_id and p.get("nameSource") == "network" and p.get("hardwareInterfaceId")}
    for key, new_name in desired.items():
        current = channels[key]
        update_object("HardwareNetworkInterface", key, {
            "name": new_name, "expected_version": current["version"],
            "capabilities": {**(current.get("capabilities") or {}), "name_source": "network", "name_network_id": network_id},
        })
    return parameters, topology
