"""Rail vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("rail", "Rail", (
    "backend.simulator.physic_lib.Industries.Rail",
))
__all__ = ["MANIFEST"]
