"""FlexRay profile and timing ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("flexray", ("flexray",), (
    "backend.nis.communication.technologies.flexray.definition",
    "backend.nis.communication.technologies.flexray.definition",
))
__all__ = ["MANIFEST"]
