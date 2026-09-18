"""Technology-specific transport ownership and canonical registry facade."""

from backend.communication.technologies import (
    DEFAULT_TECHNOLOGY_ONBOARDING,
    DEFAULT_TECHNOLOGY_REGISTRY,
    BindingResolver,
    GeneratorResolver,
    TechnologyOnboardingService,
    TechnologyRegistry,
)

from .aerospace import MANIFEST as AEROSPACE
from .building_automation import MANIFEST as BUILDING_AUTOMATION
from .can import MANIFEST as CAN
from .custom import MANIFEST as CUSTOM
from .embedded_io import MANIFEST as EMBEDDED_IO
from .energy import MANIFEST as ENERGY
from .ethernet import MANIFEST as ETHERNET
from .flexray import MANIFEST as FLEXRAY
from .industrial_automation import MANIFEST as INDUSTRIAL_AUTOMATION
from .lin import MANIFEST as LIN
from .marine import MANIFEST as MARINE
from .rail import MANIFEST as RAIL
from .robotics_ros import MANIFEST as ROBOTICS_ROS
from .wireless_iot import MANIFEST as WIRELESS_IOT

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
