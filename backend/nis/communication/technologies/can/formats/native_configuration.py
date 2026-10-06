"""Existing standalone native-export configuration, not project rate defaults."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from backend.nis.simulation.bus_technologies import normalize_technology_id
from backend.nis.simulation.hardware_profile import iter_network_interfaces as _all_interfaces
CONFIG_SCHEMA = 'communication-simulator.simulation-config.v1'
NATIVE_CAN_FORMATS = {"blf", "dbc", "asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex", "mdf", "mf4"}
NATIVE_ETHERNET_FORMATS = {"pcap", "pcapng"}
CAN_TECHNOLOGIES = {"can", "can_fd", "can_xl", "canopen", "j1939", "arinc825", "devicenet", "nmea2000"}
ETHERNET_TECHNOLOGIES = {
    "ethernet", "automotive_ethernet", "profinet", "ethercat", "ethernet_ip",
    "modbus_tcp", "arinc664_afdx", "etb", "bacnet_ip", "iec61850",
    "someip", "doip", "dds_rtps", "ipv4", "ipv6", "udp", "tcp",
}

def _native_participants(profile: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = profile.get("hardware") or []
    if len(nodes) < 2:
        return []
    participants: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        next_node = nodes[(index + 1) % len(nodes)]
        service = f"DATA_{node['id'].upper()}"
        consumed = f"DATA_{nodes[index - 1]['id'].upper()}"
        channel = 0
        for port in node.get("ports") or []:
            for interface in port.get("network_interfaces") or []:
                if normalize_technology_id(interface.get("technology")) in CAN_TECHNOLOGIES:
                    channel = int(interface.get("channel") or 0)
                    break
        participants.append(
            {
                "name": node["id"],
                "role": node.get("type") or "device",
                "channel": channel,
                "cycle_ms": int(node.get("cycle_ms") or 100),
                "provided_services": [service],
                "consumed_services": [consumed],
                "health": node.get("health") or "nominal",
                "_next": next_node["id"],
            }
        )
    for participant in participants:
        participant.pop("_next", None)
    return participants


def _native_configuration(
    config: dict[str, Any],
    profile: dict[str, Any],
    out_dir: Path,
    formats: list[str],
) -> dict[str, Any] | None:
    technologies = {
        normalize_technology_id(network.get("technology"))
        for network in profile.get("networks") or []
    }
    can_enabled = bool(technologies & CAN_TECHNOLOGIES)
    native_formats = [
        item for item in formats
        if (can_enabled and item in NATIVE_CAN_FORMATS)
    ]
    if not native_formats:
        return None
    bus = "fd"
    if "can_xl" in technologies:
        bus = "xl"
    elif can_enabled and "can_fd" not in technologies:
        bus = "classic"
    channels = 1
    for _, _, interface in _all_interfaces(profile):
        if normalize_technology_id(interface.get("technology")) in CAN_TECHNOLOGIES:
            channels = max(channels, int(interface.get("channel") or 0) + 1)
    participants = _native_participants(profile)
    return {
        "schema": CONFIG_SCHEMA,
        "simulation_mode": "restbus" if participants else "existing",
        "output_dir": str((out_dir / "native").resolve()),
        "formats": ",".join(native_formats),
        "duration_s": float(config.get("duration_s") or config.get("duration") or 1.0),
        "bus_type": bus,
        "channels": min(16, channels),
        "messages": config.get("native_messages") or config.get("messages"),
        "nominal_bitrate": int(config.get("nominal_bitrate") or 500_000),
        "data_bitrate": int(config.get("data_bitrate") or 2_000_000),
        "eth_bitrate": int(config.get("eth_bitrate") or 1_000_000_000),
        "eth_messages": config.get("eth_messages"),
        "seed": int(config.get("seed") or 42),
        "participants": participants,
        "scenario": {"domain": str(config.get("domain") or "generic")},
    }

