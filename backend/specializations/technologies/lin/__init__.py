"""LIN scheduling, capacity and transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("lin", ("lin",), (
    "backend.communication.technologies.catalog",
    "backend.engineering.capacity.lin_schedule",
    "backend.engineering.capacity.dimensioning",
    "backend.simulator.universal_trace",
))
__all__ = ["MANIFEST"]
