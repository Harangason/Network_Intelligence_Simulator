"""Explicit custom-project vocabulary and templates."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("custom", "Custom / Proprietary", (
    "backend.nis.communication.catalog",
))
__all__ = ["MANIFEST"]
