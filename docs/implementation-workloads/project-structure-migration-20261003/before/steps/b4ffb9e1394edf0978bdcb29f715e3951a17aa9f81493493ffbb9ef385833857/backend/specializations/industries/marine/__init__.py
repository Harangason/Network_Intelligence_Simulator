"""Marine vocabulary and template ownership."""

from backend.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("marine", "Marine / Off-Highway", (
    "backend.simulator.physic_lib.Industries.Marine",
))
__all__ = ["MANIFEST"]
