"""LIN scheduling, capacity and transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("lin", ("lin",), (
    "backend.nis.communication.technologies.lin.definition",
    "backend.nis.communication.technologies.lin.timing",
    "backend.nis.communication.technologies.lin.scheduling",
    "backend.nis.traces.universal_trace",
))
__all__ = ["MANIFEST"]
