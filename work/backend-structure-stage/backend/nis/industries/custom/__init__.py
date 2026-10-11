"""Explicit custom transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("custom", (
    "generic_serial", "custom_binary", "custom_text", "custom_protocol",
), ("backend.nis.communication.catalog", "backend.nis.communication.services.onboarding"))
__all__ = ["MANIFEST"]
