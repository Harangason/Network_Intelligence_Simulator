"""DDS and ROS middleware ownership."""

from backend.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("robotics_ros", ("dds", "ros2"), (
    "backend.nis.communication.catalog", "backend.nis.communication.core",
))
__all__ = ["MANIFEST"]
