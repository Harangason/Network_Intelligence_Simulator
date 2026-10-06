"""Explicit generic-networking vocabulary and templates."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("generic_networking", "Generische Kommunikationsarchitektur", (
    "backend.nis.industries.generic_networking.templates",
))
__all__ = ["MANIFEST"]
