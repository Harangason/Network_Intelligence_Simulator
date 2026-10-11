"""Industry-specific vocabulary, device and template ownership."""

from backend.specializations.industries.aerospace import MANIFEST as AEROSPACE
from backend.specializations.industries.automotive import MANIFEST as AUTOMOTIVE
from backend.specializations.industries.building_automation import MANIFEST as BUILDING_AUTOMATION
from backend.specializations.industries.custom import MANIFEST as CUSTOM
from backend.specializations.industries.embedded_systems import MANIFEST as EMBEDDED_SYSTEMS
from backend.specializations.industries.energy import MANIFEST as ENERGY
from backend.specializations.industries.generic_networking import MANIFEST as GENERIC_NETWORKING
from backend.specializations.industries.industrial_automation import MANIFEST as INDUSTRIAL_AUTOMATION
from backend.specializations.industries.iot_wireless import MANIFEST as IOT_WIRELESS
from backend.specializations.industries.marine import MANIFEST as MARINE
from backend.specializations.industries.process_industry import MANIFEST as PROCESS_INDUSTRY
from backend.specializations.industries.rail import MANIFEST as RAIL
from backend.specializations.industries.robotics_ros import MANIFEST as ROBOTICS_ROS

ALL = (
    AUTOMOTIVE, INDUSTRIAL_AUTOMATION, ROBOTICS_ROS, AEROSPACE, RAIL,
    MARINE, BUILDING_AUTOMATION, ENERGY, PROCESS_INDUSTRY,
    EMBEDDED_SYSTEMS, IOT_WIRELESS, GENERIC_NETWORKING, CUSTOM,
)

__all__ = ["ALL"]
