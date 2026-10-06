"""Process-industry vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("process_industry", "Process Industry", (
    "backend.nis.communication.catalog",
))
__all__ = ["MANIFEST"]
