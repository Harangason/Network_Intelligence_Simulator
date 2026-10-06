"""Automotive vocabulary and template ownership; transport stays separate."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("automotive", "Automotive / Vehicle", (
    "backend.nis.industries.automotive.templates",
    "backend.nis.simulation.industry_knowledge",
))
__all__ = ["MANIFEST"]
