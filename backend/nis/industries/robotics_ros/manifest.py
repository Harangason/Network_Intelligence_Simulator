"""Robotics and ROS vocabulary and template ownership."""

from backend.nis.specializations.core import IndustrySpecialization

MANIFEST = IndustrySpecialization("robotics_ros", "Robotics / ROS 2", (
    "backend.nis.industries.robotics_ros.templates",
))
__all__ = ["MANIFEST"]
