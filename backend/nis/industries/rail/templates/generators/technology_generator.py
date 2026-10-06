"""Rail bus and protocol profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class RailTechnologyGenerator(BaseTechnologyGenerator):
    domain = "rail"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('mvb', 'wtb', 'etb', 'trdp'))
