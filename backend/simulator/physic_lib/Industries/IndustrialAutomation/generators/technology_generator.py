"""Industrial automation bus and protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class IndustrialTechnologyGenerator(BaseTechnologyGenerator):
    domain = "industrial_automation"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "profibus": p("industrial", "rs485_or_fiber", "bus", "token_and_master_slave", "station_address", default_bitrate=12_000_000, max_payload_bytes=244),
            "profinet": p("industrial", "ethernet", "switched", "provider_consumer", "mac_ip_station", default_bitrate=100_000_000, max_payload_bytes=1_440, native_formats=("pcap", "pcapng")),
            "ethercat": p("industrial", "ethernet", "line_ring_star", "on_the_fly", "logical_station", default_bitrate=100_000_000, max_payload_bytes=1_486, native_formats=("pcap", "pcapng")),
            "ethernet_ip": p("industrial", "ethernet", "switched", "producer_consumer", "cip_path", default_bitrate=100_000_000, max_payload_bytes=1_400, native_formats=("pcap", "pcapng")),
            "modbus_rtu": p("industrial", "rs485", "bus", "master_slave", "unit_id", default_bitrate=115_200, max_payload_bytes=253),
            "modbus_tcp": p("industrial", "ethernet", "switched", "client_server", "ip_and_unit_id", default_bitrate=100_000_000, max_payload_bytes=260, native_formats=("pcap", "pcapng")),
            "devicenet": p("industrial", "differential_pair", "bus", "can_arbitration", "mac_id", default_bitrate=500_000, max_payload_bytes=8),
            "sercos": p("industrial", "ethernet_or_fiber", "ring_line", "time_division", "device_address", default_bitrate=100_000_000, max_payload_bytes=1_500),
            "io_link": p("industrial", "three_wire", "point_to_point", "master_device", "port_address", default_bitrate=230_400, max_payload_bytes=32),
            "opc_ua": p("industrial", "ethernet", "switched", "client_server_or_pubsub", "node_id", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
        }
