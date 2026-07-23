"""Open bus/network technology registry for the standalone simulator.

The registry deliberately separates universal simulation support from native
file writers. Every registered or custom technology can be simulated through
the neutral event model. Native formats are optional technology adapters.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


def _profile(
    family: str,
    medium: str,
    topology: str,
    access: str,
    addressing: str,
    *,
    default_bitrate: int | None = None,
    max_payload_bytes: int | None = None,
    native_formats: Iterable[str] = (),
    kind: str = "bus",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "family": family,
        "medium": medium,
        "topology": topology,
        "access": access,
        "addressing": addressing,
        "timing_model": access,
        "error_model": "technology_specific",
        "default_bitrate": default_bitrate,
        "max_payload_bytes": max_payload_bytes,
        "native_formats": list(native_formats),
    }


BUILTIN_TECHNOLOGIES: dict[str, dict[str, Any]] = {
    # Automotive and mobile systems
    "can": _profile("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=500_000, max_payload_bytes=8, native_formats=("blf", "dbc", "asc", "trc")),
    "can_fd": _profile("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=2_000_000, max_payload_bytes=64, native_formats=("blf", "dbc", "asc", "trc")),
    "can_xl": _profile("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=10_000_000, max_payload_bytes=2_048, native_formats=("jsonl", "csv")),
    "lin": _profile("automotive", "single_wire", "bus", "master_schedule", "frame_id", default_bitrate=19_200, max_payload_bytes=8),
    "flexray": _profile("automotive", "differential_pair", "bus_or_star", "time_triggered", "slot_id", default_bitrate=10_000_000, max_payload_bytes=254),
    "most": _profile("automotive", "optical_or_copper", "ring", "time_division", "node_address", default_bitrate=150_000_000),
    "automotive_ethernet": _profile("automotive", "single_or_quad_pair", "switched_star", "full_duplex", "mac_ip", default_bitrate=1_000_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
    "canopen": _profile("automotive_industrial", "differential_pair", "bus", "priority_arbitration", "node_and_cob_id", default_bitrate=500_000, max_payload_bytes=8),
    "j1939": _profile("automotive_industrial", "differential_pair", "bus", "priority_arbitration", "pgn_and_source", default_bitrate=250_000, max_payload_bytes=1_785),
    "someip": _profile("automotive", "ethernet", "switched", "transport_dependent", "service_instance_method", max_payload_bytes=1_400, native_formats=("pcap", "pcapng"), kind="protocol"),
    "doip": _profile("automotive", "ethernet", "switched", "transport_dependent", "logical_address", max_payload_bytes=4_096, native_formats=("pcap", "pcapng"), kind="protocol"),
    # Industrial automation
    "profibus": _profile("industrial", "rs485_or_fiber", "bus", "token_and_master_slave", "station_address", default_bitrate=12_000_000, max_payload_bytes=244),
    "profinet": _profile("industrial", "ethernet", "switched", "provider_consumer", "mac_ip_station", default_bitrate=100_000_000, max_payload_bytes=1_440, native_formats=("pcap", "pcapng")),
    "ethercat": _profile("industrial", "ethernet", "line_ring_star", "on_the_fly", "logical_station", default_bitrate=100_000_000, max_payload_bytes=1_486, native_formats=("pcap", "pcapng")),
    "ethernet_ip": _profile("industrial", "ethernet", "switched", "producer_consumer", "cip_path", default_bitrate=100_000_000, max_payload_bytes=1_400, native_formats=("pcap", "pcapng")),
    "modbus_rtu": _profile("industrial", "rs485", "bus", "master_slave", "unit_id", default_bitrate=115_200, max_payload_bytes=253),
    "modbus_tcp": _profile("industrial", "ethernet", "switched", "client_server", "ip_and_unit_id", default_bitrate=100_000_000, max_payload_bytes=260, native_formats=("pcap", "pcapng")),
    "devicenet": _profile("industrial", "differential_pair", "bus", "can_arbitration", "mac_id", default_bitrate=500_000, max_payload_bytes=8),
    "sercos": _profile("industrial", "ethernet_or_fiber", "ring_line", "time_division", "device_address", default_bitrate=100_000_000, max_payload_bytes=1_500),
    "io_link": _profile("industrial", "three_wire", "point_to_point", "master_device", "port_address", default_bitrate=230_400, max_payload_bytes=32),
    "opc_ua": _profile("industrial", "ethernet", "switched", "client_server_or_pubsub", "node_id", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
    # Embedded and board-level
    "i2c": _profile("embedded", "two_wire", "bus", "controller_arbitration", "7_or_10_bit_address", default_bitrate=400_000, max_payload_bytes=255),
    "spi": _profile("embedded", "synchronous_serial", "point_to_multipoint", "chip_select", "chip_select", default_bitrate=10_000_000),
    "uart": _profile("embedded", "serial", "point_to_point", "asynchronous", "none", default_bitrate=115_200),
    "rs232": _profile("embedded", "single_ended_serial", "point_to_point", "asynchronous", "none", default_bitrate=115_200),
    "rs422": _profile("embedded", "differential_serial", "point_to_multipoint", "asynchronous", "implementation_defined", default_bitrate=10_000_000),
    "rs485": _profile("embedded_industrial", "differential_serial", "bus", "implementation_defined", "implementation_defined", default_bitrate=10_000_000),
    "one_wire": _profile("embedded", "single_wire", "bus", "controller_device", "64_bit_rom", default_bitrate=16_300),
    "usb": _profile("embedded", "differential_pair", "tiered_star", "host_scheduled", "device_endpoint", default_bitrate=480_000_000, max_payload_bytes=1_024),
    "pcie": _profile("embedded", "differential_lanes", "point_to_point_fabric", "packet_switched", "bus_device_function", default_bitrate=8_000_000_000, max_payload_bytes=4_096),
    # Aerospace and defense
    "arinc429": _profile("aerospace", "shielded_twisted_pair", "point_to_point", "simplex_periodic", "label_sdi", default_bitrate=100_000, max_payload_bytes=4),
    "arinc664_afdx": _profile("aerospace", "redundant_ethernet", "switched_star", "bandwidth_allocation_gap", "virtual_link", default_bitrate=100_000_000, max_payload_bytes=1_471, native_formats=("pcap", "pcapng")),
    "arinc825": _profile("aerospace", "differential_pair", "bus", "can_arbitration", "frame_id", default_bitrate=1_000_000, max_payload_bytes=8),
    "mil_std_1553": _profile("aerospace_defense", "dual_redundant_pair", "bus", "command_response", "terminal_subaddress", default_bitrate=1_000_000, max_payload_bytes=64),
    "spacewire": _profile("aerospace", "differential_pairs", "point_to_point_network", "wormhole_routing", "path_or_logical", default_bitrate=200_000_000, max_payload_bytes=65_535),
    # Rail
    "mvb": _profile("rail", "electrical_or_fiber", "bus", "master_cycle", "device_port", default_bitrate=1_500_000, max_payload_bytes=32),
    "wtb": _profile("rail", "shielded_pair", "bus", "scheduled", "node_address", default_bitrate=1_000_000, max_payload_bytes=128),
    "etb": _profile("rail", "ethernet", "train_backbone", "switched", "mac_ip", default_bitrate=100_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
    "trdp": _profile("rail", "ethernet", "switched", "process_data_or_message_data", "com_id", default_bitrate=100_000_000, max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
    # Marine
    "nmea0183": _profile("marine", "rs422", "point_to_multipoint", "talker_listener", "sentence_id", default_bitrate=4_800, max_payload_bytes=82),
    "nmea2000": _profile("marine", "differential_pair", "bus", "can_arbitration", "pgn_and_source", default_bitrate=250_000, max_payload_bytes=223),
    "iec61162": _profile("marine", "serial_or_ethernet", "mixed", "standard_dependent", "standard_dependent", max_payload_bytes=65_535),
    # Building and energy
    "knx": _profile("building", "twisted_pair_rf_ip", "bus_line_tree", "csma_ca", "individual_and_group", default_bitrate=9_600, max_payload_bytes=255),
    "bacnet_mstp": _profile("building", "rs485", "bus", "token_passing", "mac_address", default_bitrate=115_200, max_payload_bytes=501),
    "bacnet_ip": _profile("building", "ethernet", "switched", "udp_ip", "device_instance_ip", default_bitrate=100_000_000, max_payload_bytes=1_476, native_formats=("pcap", "pcapng")),
    "iec61850": _profile("energy", "ethernet", "switched", "client_server_or_pubsub", "logical_node", default_bitrate=100_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
    "dnp3": _profile("energy", "serial_or_ip", "bus_or_network", "master_outstation", "link_address", max_payload_bytes=2_048),
    # Robotics and general networking
    "dds_rtps": _profile("robotics", "ethernet_or_ip", "switched_or_routed", "data_centric_pubsub", "domain_topic_guid", max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
    "ros2": _profile("robotics", "dds_or_custom_transport", "distributed_graph", "pubsub_service_action", "namespace_topic_node", max_payload_bytes=65_507, kind="protocol"),
    "ethernet": _profile("general", "copper_or_fiber", "switched_star", "full_duplex", "mac", default_bitrate=1_000_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
    "ipv4": _profile("general", "network_layer", "routed", "best_effort", "ipv4", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
    "ipv6": _profile("general", "network_layer", "routed", "best_effort", "ipv6", max_payload_bytes=65_575, native_formats=("pcap", "pcapng"), kind="protocol"),
    "udp": _profile("general", "transport_layer", "routed", "datagram", "port", max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
    "tcp": _profile("general", "transport_layer", "routed", "stream", "port", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
}


ALIASES = {
    "classic_can": "can",
    "can_classic": "can",
    "fd": "can_fd",
    "canfd": "can_fd",
    "xl": "can_xl",
    "canxl": "can_xl",
    "automotive ethernet": "automotive_ethernet",
    "100base_t1": "automotive_ethernet",
    "1000base_t1": "automotive_ethernet",
    "some/ip": "someip",
    "ethernet/ip": "ethernet_ip",
    "ethernetip": "ethernet_ip",
    "modbus": "modbus_rtu",
    "afdx": "arinc664_afdx",
    "arinc664": "arinc664_afdx",
    "mil1553": "mil_std_1553",
    "1553": "mil_std_1553",
    "i²c": "i2c",
    "1-wire": "one_wire",
    "nmea_0183": "nmea0183",
    "nmea_2000": "nmea2000",
    "bacnet": "bacnet_ip",
    "dds": "dds_rtps",
}


def normalize_technology_id(value: Any) -> str:
    token = str(value or "custom").strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    while "__" in token:
        token = token.replace("__", "_")
    alias_key = str(value or "").strip().lower()
    return ALIASES.get(alias_key, ALIASES.get(token, token or "custom"))


def technology_registry(custom_profiles: Iterable[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    registry = deepcopy(BUILTIN_TECHNOLOGIES)
    for raw in custom_profiles or []:
        if not isinstance(raw, dict):
            continue
        technology_id = normalize_technology_id(raw.get("id") or raw.get("name"))
        profile = {
            "kind": str(raw.get("kind") or "bus"),
            "family": str(raw.get("family") or "custom"),
            "medium": str(raw.get("medium") or "custom"),
            "topology": str(raw.get("topology") or "custom"),
            "access": str(raw.get("access") or "custom"),
            "addressing": str(raw.get("addressing") or "custom"),
            "timing_model": str(raw.get("timing_model") or raw.get("access") or "custom"),
            "error_model": str(raw.get("error_model") or "custom"),
            "default_bitrate": raw.get("default_bitrate"),
            "max_payload_bytes": raw.get("max_payload_bytes"),
            "native_formats": list(raw.get("native_formats") or []),
            "custom": True,
        }
        profile.update({key: deepcopy(value) for key, value in raw.items() if key not in {"id", "name"}})
        registry[technology_id] = profile
    return registry


def resolve_technology(value: Any, registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    technology_id = normalize_technology_id(value)
    selected = (registry or BUILTIN_TECHNOLOGIES).get(technology_id)
    if selected is None:
        return {
            "id": technology_id,
            **_profile("custom", "custom", "custom", "custom", "custom"),
            "custom": True,
            "requires_profile": True,
        }
    return {"id": technology_id, **deepcopy(selected)}


def catalog_summary(registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = registry or BUILTIN_TECHNOLOGIES
    families = sorted({str(profile.get("family") or "other") for profile in selected.values()})
    return {
        "open_registry": True,
        "custom_technologies_supported": True,
        "technology_count": len(selected),
        "families": families,
        "technologies": sorted(selected),
        "support_model": {
            "universal": "all registered and custom technologies use the neutral event trace",
            "native": "native formats are provided by optional technology-specific writers",
        },
    }
