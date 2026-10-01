"""Building automation vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("building_automation", "Building Automation", (
    "backend.simulator.physic_lib.Industries.BuildingAutomation",
))
__all__ = ["MANIFEST"]
