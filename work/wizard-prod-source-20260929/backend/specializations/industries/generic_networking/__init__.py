"""Explicit generic-networking vocabulary and templates."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("generic_networking", "Generische Kommunikationsarchitektur", (
    "backend.simulator.physic_lib.Industries.Generic",
))
__all__ = ["MANIFEST"]
