"""Embedded-systems vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("embedded_systems", "Embedded / Electronics", (
    "backend.nis.industries.embedded_systems.templates",
))
__all__ = ["MANIFEST"]
