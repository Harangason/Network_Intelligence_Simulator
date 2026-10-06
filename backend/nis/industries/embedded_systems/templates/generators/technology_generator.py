"""Embedded and board-level technology profiles."""

from backend.nis.industries.legacy_projection.generator_base import BaseTechnologyGenerator
from backend.nis.industries.legacy_projection.generator_base import TechnologyProfile


class EmbeddedTechnologyGenerator(BaseTechnologyGenerator):
    domain = "embedded_systems"

    def generate(self) -> dict[str, TechnologyProfile]:
        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles
        return legacy_profiles(('i2c', 'spi', 'uart', 'rs232', 'rs422', 'rs485', 'one_wire', 'usb', 'pcie'))
