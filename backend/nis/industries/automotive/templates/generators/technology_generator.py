"""Automotive bus and protocol profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class AutomotiveTechnologyGenerator(BaseTechnologyGenerator):
    domain = "automotive"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('can', 'can_fd', 'can_xl', 'lin', 'flexray', 'most', 'automotive_ethernet', 'canopen', 'j1939', 'someip', 'doip'))
