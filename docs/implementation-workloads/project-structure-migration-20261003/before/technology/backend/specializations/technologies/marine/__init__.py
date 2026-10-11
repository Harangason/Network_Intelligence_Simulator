"""Marine transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("marine", ("nmea0183", "nmea2000", "iec61162"), (
    "backend.communication.technologies.catalog", "backend.communication.technologies.core",
))
__all__ = ["MANIFEST"]
