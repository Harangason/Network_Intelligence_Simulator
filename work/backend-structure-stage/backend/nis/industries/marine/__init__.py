"""Marine transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("marine", ("nmea0183", "nmea2000", "iec61162"), (
    "backend.nis.communication.catalog", "backend.nis.communication.core",
))
__all__ = ["MANIFEST"]
