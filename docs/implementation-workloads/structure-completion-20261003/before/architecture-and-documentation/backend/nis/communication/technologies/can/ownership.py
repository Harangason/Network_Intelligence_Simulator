"""CAN-family profiles, arbitration, capacity and native formats."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("can", (
    "can", "can_fd", "can_xl", "canopen", "j1939", "isobus",
    "devicenet", "arinc825", "can_aerospace", "nmea2000", "generic_can",
    "most", "uds", "xcp", "ccp", "obd2",
), (
    "backend.nis.communication.catalog",
    "backend.nis.simulation.runtime.event_scheduler",
    "backend.nis.engineering.capacity.calculators",
    "backend.nis.communication.technologies.can.formats.can_format_writers",
))
__all__ = ["MANIFEST"]
