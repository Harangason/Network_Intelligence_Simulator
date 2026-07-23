"""Standalone hardware, port, network-interface and network normalization."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from bus_technologies import normalize_technology_id, resolve_technology, technology_registry


HARDWARE_SCHEMA = "communication-simulator.hardware.v1"


def _identifier(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", str(value or fallback).strip()).strip("_.:")
    return text or fallback


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _first_list(*values: Any) -> list[dict[str, Any]]:
    for value in values:
        records = _list_of_dicts(value)
        if records:
            return records
    return []


def normalize_hardware_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize external hardware without mutating the source configuration."""

    raw = deepcopy(config or {})
    raw_hardware = raw.get("hardware")
    hardware_container = raw_hardware if isinstance(raw_hardware, dict) else {}
    nodes = _first_list(
        raw_hardware if isinstance(raw_hardware, list) else None,
        hardware_container.get("nodes"),
        raw.get("nodes"),
        raw.get("devices"),
        raw.get("ecus"),
        raw.get("controllers"),
        raw.get("hardware_nodes"),
    )
    networks = _first_list(
        raw.get("networks"),
        raw.get("buses"),
        hardware_container.get("networks"),
        hardware_container.get("buses"),
    )
    custom_profiles = _first_list(raw.get("technology_profiles"), hardware_container.get("technology_profiles"))

    normalized_networks: list[dict[str, Any]] = []
    for index, network in enumerate(networks):
        item = deepcopy(network)
        item["id"] = _identifier(item.get("id") or item.get("name"), f"network_{index + 1}")
        item.setdefault("name", item["id"])
        item["technology"] = normalize_technology_id(
            item.get("technology") or item.get("type") or item.get("protocol") or "custom"
        )
        if item.get("bitrate") is None:
            for alias in ("speed_bps", "nominal_bitrate", "data_rate"):
                if item.get(alias) is not None:
                    item["bitrate"] = item[alias]
                    break
        normalized_networks.append(item)

    normalized_nodes: list[dict[str, Any]] = []
    for node_index, node in enumerate(nodes):
        item = deepcopy(node)
        item["id"] = _identifier(item.get("id") or item.get("name"), f"hardware_{node_index + 1}")
        item.setdefault("name", item["id"])
        item.setdefault("type", item.get("hardware_type") or item.get("role") or "device")
        item.setdefault("health", "nominal")
        raw_ports = _first_list(item.get("ports"), item.get("connectors"))
        normalized_ports: list[dict[str, Any]] = []
        for port_index, port in enumerate(raw_ports):
            normalized_port = deepcopy(port)
            normalized_port["id"] = _identifier(
                normalized_port.get("id") or normalized_port.get("name"),
                f"{item['id']}_port_{port_index + 1}",
            )
            normalized_port.setdefault("name", normalized_port["id"])
            normalized_port.setdefault(
                "physical_type",
                normalized_port.get("type") or normalized_port.get("medium") or "generic",
            )
            raw_interfaces = _first_list(
                normalized_port.get("network_interfaces"),
                normalized_port.get("interfaces"),
                normalized_port.get("logical_interfaces"),
            )
            normalized_interfaces: list[dict[str, Any]] = []
            for interface_index, interface in enumerate(raw_interfaces):
                normalized_interface = deepcopy(interface)
                normalized_interface["id"] = _identifier(
                    normalized_interface.get("id") or normalized_interface.get("name"),
                    f"{normalized_port['id']}_if_{interface_index + 1}",
                )
                normalized_interface.setdefault("name", normalized_interface["id"])
                normalized_interface["technology"] = normalize_technology_id(
                    normalized_interface.get("technology")
                    or normalized_interface.get("protocol")
                    or normalized_port.get("technology")
                    or normalized_port.get("type")
                    or "custom"
                )
                network_value = (
                    normalized_interface.get("network")
                    or normalized_interface.get("network_id")
                    or normalized_interface.get("bus")
                    or normalized_interface.get("bus_name")
                )
                if network_value is not None:
                    normalized_interface["network"] = _identifier(network_value, str(network_value))
                normalized_interfaces.append(normalized_interface)
            normalized_port["network_interfaces"] = normalized_interfaces
            for alias in ("interfaces", "logical_interfaces"):
                normalized_port.pop(alias, None)
            normalized_ports.append(normalized_port)
        item["ports"] = normalized_ports
        item.pop("connectors", None)
        normalized_nodes.append(item)

    return {
        "schema": HARDWARE_SCHEMA,
        "source_policy": "preserve_external_definition",
        "hardware": normalized_nodes,
        "networks": normalized_networks,
        "technology_profiles": custom_profiles,
    }


def contains_hardware_records(config: dict[str, Any] | None) -> bool:
    profile = normalize_hardware_config(config)
    return bool(profile["hardware"] or profile["networks"])


def iter_network_interfaces(profile: dict[str, Any]):
    for node in profile.get("hardware") or []:
        for port in node.get("ports") or []:
            for interface in port.get("network_interfaces") or []:
                yield node, port, interface


def hardware_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    interfaces = list(iter_network_interfaces(profile))
    technologies = {
        normalize_technology_id(network.get("technology"))
        for network in profile.get("networks") or []
        if isinstance(network, dict)
    }
    technologies.update(
        normalize_technology_id(interface.get("technology"))
        for _, _, interface in interfaces
    )
    return {
        "enabled": bool(profile.get("hardware") or profile.get("networks")),
        "schema": HARDWARE_SCHEMA,
        "source_policy": "external definitions are preserved and normalized without changing their intent",
        "hardware_components": len(profile.get("hardware") or []),
        "ports": sum(len(node.get("ports") or []) for node in profile.get("hardware") or []),
        "network_interfaces": len(interfaces),
        "networks": len(profile.get("networks") or []),
        "technologies": sorted(technologies),
    }


def validate_hardware_profile(profile: dict[str, Any]) -> dict[str, Any]:
    registry = technology_registry(profile.get("technology_profiles"))
    findings: list[dict[str, Any]] = []
    network_by_id: dict[str, dict[str, Any]] = {}
    network_ids: set[str] = set()
    hardware_ids: set[str] = set()
    port_ids: set[str] = set()
    interface_ids: set[str] = set()

    def finding(code: str, severity: str, message: str, **context: Any) -> None:
        findings.append({"code": code, "severity": severity, "message": message, **context})

    for network in profile.get("networks") or []:
        network_id = str(network.get("id") or "")
        if network_id in network_ids:
            finding("duplicate_network_id", "error", f"Network id '{network_id}' is duplicated.", network=network_id)
        network_ids.add(network_id)
        network_by_id[network_id] = network
        resolved = resolve_technology(network.get("technology"), registry)
        if resolved.get("requires_profile"):
            finding(
                "missing_technology_profile",
                "warning",
                f"Technology '{resolved['id']}' has no built-in or custom profile; generic defaults are used.",
                network=network_id,
                technology=resolved["id"],
            )

    used_networks: set[str] = set()
    for node in profile.get("hardware") or []:
        node_id = str(node.get("id") or "")
        if node_id in hardware_ids:
            finding("duplicate_hardware_id", "error", f"Hardware id '{node_id}' is duplicated.", hardware=node_id)
        hardware_ids.add(node_id)
        if not node.get("ports"):
            finding("hardware_without_ports", "info", f"Hardware '{node_id}' has no physical ports.", hardware=node_id)
        for port in node.get("ports") or []:
            port_id = str(port.get("id") or "")
            if port_id in port_ids:
                finding("duplicate_port_id", "error", f"Port id '{port_id}' is duplicated.", hardware=node_id, port=port_id)
            port_ids.add(port_id)
            if not port.get("network_interfaces"):
                finding("port_without_interface", "info", f"Port '{port_id}' has no network interface.", hardware=node_id, port=port_id)
            for interface in port.get("network_interfaces") or []:
                interface_id = str(interface.get("id") or "")
                if interface_id in interface_ids:
                    finding("duplicate_interface_id", "error", f"Interface id '{interface_id}' is duplicated.", interface=interface_id)
                interface_ids.add(interface_id)
                network_id = str(interface.get("network") or "")
                if not network_id:
                    finding("interface_without_network", "warning", f"Interface '{interface_id}' is not assigned to a network.", interface=interface_id)
                elif network_id not in network_ids:
                    finding("unknown_network", "error", f"Interface '{interface_id}' references unknown network '{network_id}'.", interface=interface_id, network=network_id)
                else:
                    used_networks.add(network_id)
                technology = resolve_technology(interface.get("technology"), registry)
                if technology.get("requires_profile"):
                    finding(
                        "missing_technology_profile",
                        "warning",
                        f"Interface '{interface_id}' uses technology '{technology['id']}' without a profile.",
                        interface=interface_id,
                        technology=technology["id"],
                    )
                if network_id in network_by_id:
                    network_technology = resolve_technology(network_by_id[network_id].get("technology"), registry)
                    if (
                        technology["id"] != network_technology["id"]
                        and technology.get("kind") == "bus"
                        and network_technology.get("kind") == "bus"
                    ):
                        finding(
                            "interface_network_technology_mismatch",
                            "warning",
                            f"Interface '{interface_id}' uses '{technology['id']}' on network technology '{network_technology['id']}'.",
                            interface=interface_id,
                            network=network_id,
                        )
                    capabilities = port.get("capabilities") if isinstance(port.get("capabilities"), dict) else {}
                    supported = capabilities.get("supported_technologies") or capabilities.get("protocols")
                    if isinstance(supported, list):
                        normalized_supported = {normalize_technology_id(item) for item in supported}
                        if technology["id"] not in normalized_supported:
                            finding(
                                "unsupported_port_technology",
                                "error",
                                f"Port '{port_id}' does not declare support for '{technology['id']}'.",
                                hardware=node_id,
                                port=port_id,
                                interface=interface_id,
                            )
                    flag_by_technology = {
                        "can": "classic_can",
                        "can_fd": "can_fd",
                        "can_xl": "can_xl",
                    }
                    capability_flag = flag_by_technology.get(technology["id"])
                    if capability_flag in capabilities and capabilities[capability_flag] is False:
                        finding(
                            "unsupported_port_technology",
                            "error",
                            f"Port '{port_id}' explicitly disables '{technology['id']}'.",
                            hardware=node_id,
                            port=port_id,
                            interface=interface_id,
                        )
                    network = network_by_id[network_id]
                    bitrate = (
                        network.get("data_bitrate")
                        or network.get("bitrate")
                        or network.get("speed_bps")
                        or network.get("nominal_bitrate")
                    )
                    max_bitrate = (
                        capabilities.get("max_data_bitrate")
                        or capabilities.get("max_bitrate")
                        or capabilities.get("speed_bps")
                    )
                    if bitrate is not None and max_bitrate is not None:
                        try:
                            if int(bitrate) > int(max_bitrate):
                                finding(
                                    "port_bitrate_exceeded",
                                    "error",
                                    f"Network '{network_id}' bitrate {bitrate} exceeds port '{port_id}' capability {max_bitrate}.",
                                    hardware=node_id,
                                    port=port_id,
                                    interface=interface_id,
                                    network=network_id,
                                )
                        except (TypeError, ValueError):
                            finding(
                                "invalid_bitrate",
                                "warning",
                                f"Bitrate for network '{network_id}' or port '{port_id}' is not numeric.",
                                network=network_id,
                                port=port_id,
                            )

    for network_id in sorted(network_ids - used_networks):
        finding("unused_network", "info", f"Network '{network_id}' has no attached interface.", network=network_id)

    severity_counts = {
        severity: sum(1 for item in findings if item["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    return {
        "valid": severity_counts["error"] == 0,
        "mode": "non_invasive_validation",
        "source_policy": "source data is never modified automatically",
        "severity_counts": severity_counts,
        "findings": findings,
    }
