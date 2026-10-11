"""Energy and process-industry transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("energy", (
    "iec61850", "mms", "goose", "sampled_values", "dnp3", "iec60870_5_101",
    "iec60870_5_104", "sunspec_modbus", "ocpp", "hart", "wirelesshart",
    "foundation_fieldbus_h1",
), ("backend.nis.communication.catalog", "backend.nis.communication.core"))
__all__ = ["MANIFEST"]
