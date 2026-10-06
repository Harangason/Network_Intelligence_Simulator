"""Aerospace and avionics vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("aerospace", "Aerospace / Avionics", (
    "backend.nis.industries.aerospace.templates",
))
__all__ = ["MANIFEST"]
