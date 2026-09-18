"""DDS and ROS middleware ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("robotics_ros", ("dds", "ros2"), (
    "backend.communication.technologies.catalog", "backend.communication.technologies.core",
))
__all__ = ["MANIFEST"]
