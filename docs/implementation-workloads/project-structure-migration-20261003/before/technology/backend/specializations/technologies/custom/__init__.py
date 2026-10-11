"""Explicit custom transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("custom", (
    "generic_serial", "custom_binary", "custom_text", "custom_protocol",
), ("backend.communication.technologies.catalog", "backend.communication.technologies.onboarding"))
__all__ = ["MANIFEST"]
