"""Industrial automation bus and protocol profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class IndustrialTechnologyGenerator(BaseTechnologyGenerator):
    domain = "industrial_automation"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('profibus', 'profinet', 'ethercat', 'ethernet_ip', 'modbus_rtu', 'modbus_tcp', 'devicenet', 'sercos', 'io_link', 'opc_ua'))
