"""Automotive vocabulary and template ownership; transport stays separate."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("automotive", "Automotive / Vehicle", (
    "backend.simulator.physic_lib.Industries.Automotive",
    "backend.simulator.industry_knowledge",
))
__all__ = ["MANIFEST"]
