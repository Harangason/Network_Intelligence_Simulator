"""Technology-specific transport ownership and canonical registry facade."""

from backend.nis.communication import (
    DEFAULT_TECHNOLOGY_ONBOARDING,
    DEFAULT_TECHNOLOGY_REGISTRY,
    BindingResolver,
    GeneratorResolver,
    TechnologyOnboardingService,
    TechnologyRegistry,
)

from backend.nis.industries.aerospace.technology_refs import MANIFEST as AEROSPACE
from backend.nis.industries.building_automation.technology_refs import MANIFEST as BUILDING_AUTOMATION
from backend.nis.communication.technologies.can.ownership import MANIFEST as CAN
from backend.nis.industries.custom.technology_refs import MANIFEST as CUSTOM
from backend.nis.industries.embedded_systems.technology_refs import MANIFEST as EMBEDDED_IO
from backend.nis.industries.energy.technology_refs import MANIFEST as ENERGY
from backend.nis.communication.technologies.ethernet.ownership import MANIFEST as ETHERNET
from backend.nis.communication.technologies.flexray.ownership import MANIFEST as FLEXRAY
from backend.nis.industries.industrial_automation.technology_refs import MANIFEST as INDUSTRIAL_AUTOMATION
from backend.nis.communication.technologies.lin.ownership import MANIFEST as LIN
from backend.nis.industries.marine.technology_refs import MANIFEST as MARINE
from backend.nis.industries.rail.technology_refs import MANIFEST as RAIL
from backend.nis.industries.robotics_ros.technology_refs import MANIFEST as ROBOTICS_ROS
from backend.nis.industries.iot_wireless.technology_refs import MANIFEST as WIRELESS_IOT

ALL = (
    CAN, LIN, FLEXRAY, ETHERNET, INDUSTRIAL_AUTOMATION, EMBEDDED_IO,
    AEROSPACE, RAIL, MARINE, BUILDING_AUTOMATION, ENERGY, ROBOTICS_ROS,
    WIRELESS_IOT, CUSTOM,
)

__all__ = [
    "ALL", "BindingResolver", "DEFAULT_TECHNOLOGY_ONBOARDING",
    "DEFAULT_TECHNOLOGY_REGISTRY", "GeneratorResolver",
    "TechnologyOnboardingService", "TechnologyRegistry",
]
