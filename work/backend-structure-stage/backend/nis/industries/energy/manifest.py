"""Energy and smart-grid vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("energy", "Energy / Smart Grid", (
    "backend.nis.industries.energy.templates",
))
__all__ = ["MANIFEST"]
