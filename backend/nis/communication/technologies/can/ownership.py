"""CAN-family profiles, arbitration, capacity and native formats."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("can", (
    "can", "can_fd", "can_xl", "canopen", "j1939", "isobus",
    "devicenet", "arinc825", "can_aerospace", "nmea2000", "generic_can",
    "most", "uds", "xcp", "ccp", "obd2",
), (
    "backend.nis.communication.technologies.can.definition",
    "backend.nis.communication.technologies.can.arbitration",
    "backend.nis.communication.technologies.can.timing",
    "backend.nis.communication.technologies.can.scheduling",
    "backend.nis.communication.technologies.can_fd.timing",
    "backend.nis.communication.technologies.can.formats.can_format_writers",
))
__all__ = ["MANIFEST"]
