"""FlexRay profile and timing ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("flexray", ("flexray",), (
    "backend.nis.communication.catalog",
    "backend.nis.engineering.capacity.calculators",
))
__all__ = ["MANIFEST"]
