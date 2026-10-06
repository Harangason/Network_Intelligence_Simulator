"""Generic Ethernet, network and transport profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class GenericNetworkTechnologyGenerator(BaseTechnologyGenerator):
    domain = "generic_networking"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('ethernet', 'ipv4', 'ipv6', 'udp', 'tcp'))
