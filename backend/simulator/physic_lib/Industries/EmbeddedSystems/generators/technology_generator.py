"""Embedded and board-level technology profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class EmbeddedTechnologyGenerator(BaseTechnologyGenerator):
    domain = "embedded_systems"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "i2c": p("embedded", "two_wire", "bus", "controller_arbitration", "7_or_10_bit_address", default_bitrate=400_000, max_payload_bytes=255),
            "spi": p("embedded", "synchronous_serial", "point_to_multipoint", "chip_select", "chip_select", default_bitrate=10_000_000),
            "uart": p("embedded", "serial", "point_to_point", "asynchronous", "none", default_bitrate=115_200),
            "rs232": p("embedded", "single_ended_serial", "point_to_point", "asynchronous", "none", default_bitrate=115_200),
            "rs422": p("embedded", "differential_serial", "point_to_multipoint", "asynchronous", "implementation_defined", default_bitrate=10_000_000),
            "rs485": p("embedded_industrial", "differential_serial", "bus", "implementation_defined", "implementation_defined", default_bitrate=10_000_000),
            "one_wire": p("embedded", "single_wire", "bus", "controller_device", "64_bit_rom", default_bitrate=16_300),
            "usb": p("embedded", "differential_pair", "tiered_star", "host_scheduled", "device_endpoint", default_bitrate=480_000_000, max_payload_bytes=1_024),
            "pcie": p("embedded", "differential_lanes", "point_to_point_fabric", "packet_switched", "bus_device_function", default_bitrate=8_000_000_000, max_payload_bytes=4_096),
        }
