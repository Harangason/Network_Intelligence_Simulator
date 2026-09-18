"""Industrial automation vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("industrial_automation", "Industrial Automation / SPS", (
    "backend.simulator.physic_lib.Industries.IndustrialAutomation",
))
__all__ = ["MANIFEST"]
