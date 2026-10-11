"""Energy and smart-grid vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("energy", "Energy / Smart Grid", (
    "backend.simulator.physic_lib.Industries.Energy",
))
__all__ = ["MANIFEST"]
