"""LIN scheduling, capacity and transport ownership."""

from backend.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("lin", ("lin",), (
    "backend.nis.communication.catalog",
    "backend.engineering.capacity.lin_schedule",
    "backend.engineering.capacity.dimensioning",
    "backend.simulator.universal_trace",
))
__all__ = ["MANIFEST"]
