"""Automotive bus and protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class AutomotiveTechnologyGenerator(BaseTechnologyGenerator):
    domain = "automotive"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "can": p("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=500_000, max_payload_bytes=8, native_formats=("blf", "dbc", "asc", "trc")),
            "can_fd": p("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=2_000_000, max_payload_bytes=64, native_formats=("blf", "dbc", "asc", "trc")),
            "can_xl": p("automotive", "differential_pair", "bus", "priority_arbitration", "frame_id", default_bitrate=10_000_000, max_payload_bytes=2_048, native_formats=("jsonl", "csv")),
            "lin": p("automotive", "single_wire", "bus", "master_schedule", "frame_id", default_bitrate=19_200, max_payload_bytes=8),
            "flexray": p("automotive", "differential_pair", "bus_or_star", "time_triggered", "slot_id", default_bitrate=10_000_000, max_payload_bytes=254),
            "most": p("automotive", "optical_or_copper", "ring", "time_division", "node_address", default_bitrate=150_000_000),
            "automotive_ethernet": p("automotive", "single_or_quad_pair", "switched_star", "full_duplex", "mac_ip", default_bitrate=1_000_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
            "canopen": p("automotive_industrial", "differential_pair", "bus", "priority_arbitration", "node_and_cob_id", default_bitrate=500_000, max_payload_bytes=8),
            "j1939": p("automotive_industrial", "differential_pair", "bus", "priority_arbitration", "pgn_and_source", default_bitrate=250_000, max_payload_bytes=1_785),
            "someip": p("automotive", "ethernet", "switched", "transport_dependent", "service_instance_method", max_payload_bytes=1_400, native_formats=("pcap", "pcapng"), kind="protocol"),
            "doip": p("automotive", "ethernet", "switched", "transport_dependent", "logical_address", max_payload_bytes=4_096, native_formats=("pcap", "pcapng"), kind="protocol"),
        }
