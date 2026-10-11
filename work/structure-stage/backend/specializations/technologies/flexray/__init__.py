"""FlexRay profile and timing ownership."""

from backend.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("flexray", ("flexray",), (
    "backend.nis.communication.catalog",
    "backend.engineering.capacity.calculators",
))
__all__ = ["MANIFEST"]
