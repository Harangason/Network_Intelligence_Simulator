"""Industry-specific vocabulary, device and template ownership."""

from .aerospace import MANIFEST as AEROSPACE
from .automotive import MANIFEST as AUTOMOTIVE
from .building_automation import MANIFEST as BUILDING_AUTOMATION
from .custom import MANIFEST as CUSTOM
from .embedded_systems import MANIFEST as EMBEDDED_SYSTEMS
from .energy import MANIFEST as ENERGY
from .generic_networking import MANIFEST as GENERIC_NETWORKING
from .industrial_automation import MANIFEST as INDUSTRIAL_AUTOMATION
from .iot_wireless import MANIFEST as IOT_WIRELESS
from .marine import MANIFEST as MARINE
from .process_industry import MANIFEST as PROCESS_INDUSTRY
from .rail import MANIFEST as RAIL
from .robotics_ros import MANIFEST as ROBOTICS_ROS

ALL = (
    AUTOMOTIVE, INDUSTRIAL_AUTOMATION, ROBOTICS_ROS, AEROSPACE, RAIL,
    MARINE, BUILDING_AUTOMATION, ENERGY, PROCESS_INDUSTRY,
    EMBEDDED_SYSTEMS, IOT_WIRELESS, GENERIC_NETWORKING, CUSTOM,
)

__all__ = ["ALL"]
