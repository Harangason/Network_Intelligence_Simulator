"""Board-level and embedded I/O technology ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("embedded_io", (
    "i2c", "i3c", "spi", "uart", "rs232", "rs422", "rs485", "one_wire",
    "usb", "pcie", "mipi_csi2", "mipi_dsi", "lvds", "gpio", "pwm", "adc", "dac",
), ("backend.communication.technologies.catalog", "backend.communication.technologies.core"))
__all__ = ["MANIFEST"]
