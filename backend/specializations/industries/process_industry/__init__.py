"""Process-industry vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("process_industry", "Process Industry", (
    "backend.communication.technologies.catalog",
))
__all__ = ["MANIFEST"]
