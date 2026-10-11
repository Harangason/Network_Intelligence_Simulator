"""Rail bus and protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class RailTechnologyGenerator(BaseTechnologyGenerator):
    domain = "rail"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "mvb": p("rail", "electrical_or_fiber", "bus", "master_cycle", "device_port", default_bitrate=1_500_000, max_payload_bytes=32),
            "wtb": p("rail", "shielded_pair", "bus", "scheduled", "node_address", default_bitrate=1_000_000, max_payload_bytes=128),
            "etb": p("rail", "ethernet", "train_backbone", "switched", "mac_ip", default_bitrate=100_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
            "trdp": p("rail", "ethernet", "switched", "process_data_or_message_data", "com_id", default_bitrate=100_000_000, max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
        }
