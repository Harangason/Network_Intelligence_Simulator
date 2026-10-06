"""Ethernet, IP transport and capture ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("ethernet", (
    "ethernet", "ip", "udp", "tcp", "someip", "someip_sd", "doip",
    "avb", "tsn", "generic_ethernet", "custom_udp", "custom_tcp",
), (
    "backend.nis.communication.catalog",
    "backend.nis.communication.technologies.ethernet.transport",
    "backend.nis.communication.technologies.ethernet.formats.eth_format_writers",
))
__all__ = ["MANIFEST"]
