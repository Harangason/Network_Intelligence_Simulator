"""Marine bus and protocol profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class MarineTechnologyGenerator(BaseTechnologyGenerator):
    domain = "marine"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('nmea0183', 'nmea2000', 'iec61162'))
