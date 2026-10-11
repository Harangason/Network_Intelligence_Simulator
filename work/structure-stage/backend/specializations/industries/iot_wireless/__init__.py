"""IoT and wireless vocabulary and template ownership."""

from backend.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("iot_wireless", "IoT / Edge / Wireless", (
    "backend.nis.communication.catalog",
))
__all__ = ["MANIFEST"]
