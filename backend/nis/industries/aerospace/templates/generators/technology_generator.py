"""Aerospace and defense bus profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class AerospaceTechnologyGenerator(BaseTechnologyGenerator):
    domain = "aerospace"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('arinc429', 'arinc664_afdx', 'arinc825', 'mil_std_1553', 'spacewire'))
