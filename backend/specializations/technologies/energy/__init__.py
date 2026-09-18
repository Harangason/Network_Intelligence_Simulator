"""Energy and process-industry transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("energy", (
    "iec61850", "mms", "goose", "sampled_values", "dnp3", "iec60870_5_101",
    "iec60870_5_104", "sunspec_modbus", "ocpp", "hart", "wirelesshart",
    "foundation_fieldbus_h1",
), ("backend.communication.technologies.catalog", "backend.communication.technologies.core"))
__all__ = ["MANIFEST"]
