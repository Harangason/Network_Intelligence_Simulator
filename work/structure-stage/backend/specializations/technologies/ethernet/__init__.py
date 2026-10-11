"""Ethernet, IP transport and capture ownership."""

from backend.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("ethernet", (
    "ethernet", "ip", "udp", "tcp", "someip", "someip_sd", "doip",
    "avb", "tsn", "generic_ethernet", "custom_udp", "custom_tcp",
), (
    "backend.nis.communication.catalog",
    "backend.simulator.ethernet_transport",
    "backend.simulator.format_generators.eth_format_writers",
))
__all__ = ["MANIFEST"]
