"""Building automation bus profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class BuildingTechnologyGenerator(BaseTechnologyGenerator):
    domain = "building_automation"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('knx', 'bacnet_mstp', 'bacnet_ip'))
