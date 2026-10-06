"""Building-automation transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("building_automation", (
    "bacnet_ip", "bacnet_mstp", "bacnet_sc", "knx_tp", "knx_ip", "knx_rf",
    "lonworks", "dali", "m_bus", "wireless_m_bus",
), ("backend.nis.communication.catalog", "backend.nis.communication.core"))
__all__ = ["MANIFEST"]
