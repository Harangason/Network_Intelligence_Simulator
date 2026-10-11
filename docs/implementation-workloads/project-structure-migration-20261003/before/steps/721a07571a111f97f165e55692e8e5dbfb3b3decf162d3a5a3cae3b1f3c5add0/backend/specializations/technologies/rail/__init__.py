"""Rail transport ownership."""

from backend.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("rail", ("mvb", "wtb", "etb", "trdp"), (
    "backend.nis.communication.catalog", "backend.nis.communication.core",
))
__all__ = ["MANIFEST"]
