"""Marine vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("marine", "Marine / Off-Highway", (
    "backend.nis.industries.marine.templates",
))
__all__ = ["MANIFEST"]
