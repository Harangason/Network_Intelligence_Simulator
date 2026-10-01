"""Building-automation transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("building_automation", (
    "bacnet_ip", "bacnet_mstp", "bacnet_sc", "knx_tp", "knx_ip", "knx_rf",
    "lonworks", "dali", "m_bus", "wireless_m_bus",
), ("backend.communication.technologies.catalog", "backend.communication.technologies.core"))
__all__ = ["MANIFEST"]
