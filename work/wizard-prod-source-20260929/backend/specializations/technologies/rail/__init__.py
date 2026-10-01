"""Rail transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("rail", ("mvb", "wtb", "etb", "trdp"), (
    "backend.communication.technologies.catalog", "backend.communication.technologies.core",
))
__all__ = ["MANIFEST"]
