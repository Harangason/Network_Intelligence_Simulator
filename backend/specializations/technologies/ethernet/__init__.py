"""Ethernet, IP transport and capture ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("ethernet", (
    "ethernet", "ip", "udp", "tcp", "someip", "someip_sd", "doip",
    "avb", "tsn", "generic_ethernet", "custom_udp", "custom_tcp",
), (
    "backend.communication.technologies.catalog",
    "backend.simulator.ethernet_transport",
    "backend.simulator.format_generators.eth_format_writers",
))
__all__ = ["MANIFEST"]
