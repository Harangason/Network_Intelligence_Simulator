"""Robotics and ROS vocabulary and template ownership."""

from ...core import IndustrySpecialization

MANIFEST = IndustrySpecialization("robotics_ros", "Robotics / ROS 2", (
    "backend.simulator.physic_lib.Industries.RoboticsROS",
))
__all__ = ["MANIFEST"]
