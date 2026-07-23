"""Building automation bus profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class BuildingTechnologyGenerator(BaseTechnologyGenerator):
    domain = "building_automation"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "knx": p("building", "twisted_pair_rf_ip", "bus_line_tree", "csma_ca", "individual_and_group", default_bitrate=9_600, max_payload_bytes=255),
            "bacnet_mstp": p("building", "rs485", "bus", "token_passing", "mac_address", default_bitrate=115_200, max_payload_bytes=501),
            "bacnet_ip": p("building", "ethernet", "switched", "udp_ip", "device_instance_ip", default_bitrate=100_000_000, max_payload_bytes=1_476, native_formats=("pcap", "pcapng")),
        }
