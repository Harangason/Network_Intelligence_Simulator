"""Rail vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("rail", "Rail", (
    "backend.nis.industries.rail.templates",
))
__all__ = ["MANIFEST"]
