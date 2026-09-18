"""Explicit custom-project vocabulary and templates."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("custom", "Custom / Proprietary", (
    "backend.communication.technologies.catalog",
))
__all__ = ["MANIFEST"]
