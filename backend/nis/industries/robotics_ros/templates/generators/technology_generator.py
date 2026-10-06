"""Robotics middleware protocol profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class RoboticsTechnologyGenerator(BaseTechnologyGenerator):
    domain = "robotics_ros"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('dds_rtps', 'ros2'))
