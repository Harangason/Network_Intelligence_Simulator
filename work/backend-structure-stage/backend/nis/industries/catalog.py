"""Industry-specific vocabulary, device and template ownership."""

from backend.nis.industries.aerospace.manifest import MANIFEST as AEROSPACE
from backend.nis.industries.automotive.manifest import MANIFEST as AUTOMOTIVE
from backend.nis.industries.building_automation.manifest import MANIFEST as BUILDING_AUTOMATION
from backend.nis.industries.custom.manifest import MANIFEST as CUSTOM
from backend.nis.industries.embedded_systems.manifest import MANIFEST as EMBEDDED_SYSTEMS
from backend.nis.industries.energy.manifest import MANIFEST as ENERGY
from backend.nis.industries.generic_networking.manifest import MANIFEST as GENERIC_NETWORKING
from backend.nis.industries.industrial_automation.manifest import MANIFEST as INDUSTRIAL_AUTOMATION
from backend.nis.industries.iot_wireless.manifest import MANIFEST as IOT_WIRELESS
from backend.nis.industries.marine.manifest import MANIFEST as MARINE
from backend.nis.industries.process_industry.manifest import MANIFEST as PROCESS_INDUSTRY
from backend.nis.industries.rail.manifest import MANIFEST as RAIL
from backend.nis.industries.robotics_ros.manifest import MANIFEST as ROBOTICS_ROS

ALL = (
    AUTOMOTIVE, INDUSTRIAL_AUTOMATION, ROBOTICS_ROS, AEROSPACE, RAIL,
    MARINE, BUILDING_AUTOMATION, ENERGY, PROCESS_INDUSTRY,
    EMBEDDED_SYSTEMS, IOT_WIRELESS, GENERIC_NETWORKING, CUSTOM,
)

__all__ = ["ALL"]
