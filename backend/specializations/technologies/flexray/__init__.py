"""FlexRay profile and timing ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("flexray", ("flexray",), (
    "backend.communication.technologies.catalog",
    "backend.engineering.capacity.calculators",
))
__all__ = ["MANIFEST"]
