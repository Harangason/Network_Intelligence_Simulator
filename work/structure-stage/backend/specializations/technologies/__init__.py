"""Technology-specific transport ownership and canonical registry facade."""

from backend.nis.communication import (
    DEFAULT_TECHNOLOGY_ONBOARDING,
    DEFAULT_TECHNOLOGY_REGISTRY,
    BindingResolver,
    GeneratorResolver,
    TechnologyOnboardingService,
    TechnologyRegistry,
)

from backend.specializations.technologies.aerospace import MANIFEST as AEROSPACE
from backend.specializations.technologies.building_automation import MANIFEST as BUILDING_AUTOMATION
from backend.specializations.technologies.can import MANIFEST as CAN
from backend.specializations.technologies.custom import MANIFEST as CUSTOM
from backend.specializations.technologies.embedded_io import MANIFEST as EMBEDDED_IO
from backend.specializations.technologies.energy import MANIFEST as ENERGY
from backend.specializations.technologies.ethernet import MANIFEST as ETHERNET
from backend.specializations.technologies.flexray import MANIFEST as FLEXRAY
from backend.specializations.technologies.industrial_automation import MANIFEST as INDUSTRIAL_AUTOMATION
from backend.specializations.technologies.lin import MANIFEST as LIN
from backend.specializations.technologies.marine import MANIFEST as MARINE
from backend.specializations.technologies.rail import MANIFEST as RAIL
from backend.specializations.technologies.robotics_ros import MANIFEST as ROBOTICS_ROS
from backend.specializations.technologies.wireless_iot import MANIFEST as WIRELESS_IOT

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
