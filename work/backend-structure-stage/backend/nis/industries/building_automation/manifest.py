"""Building automation vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("building_automation", "Building Automation", (
    "backend.nis.industries.building_automation.templates",
))
__all__ = ["MANIFEST"]
