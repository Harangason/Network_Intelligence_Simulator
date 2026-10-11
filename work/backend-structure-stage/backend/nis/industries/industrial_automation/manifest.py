"""Industrial automation vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("industrial_automation", "Industrial Automation / SPS", (
    "backend.nis.industries.industrial_automation.templates",
))
__all__ = ["MANIFEST"]
