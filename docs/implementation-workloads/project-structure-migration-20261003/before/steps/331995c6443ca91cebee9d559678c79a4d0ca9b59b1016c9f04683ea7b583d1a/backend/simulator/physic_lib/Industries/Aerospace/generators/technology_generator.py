"""Aerospace and defense bus profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class AerospaceTechnologyGenerator(BaseTechnologyGenerator):
    domain = "aerospace"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "arinc429": p("aerospace", "shielded_twisted_pair", "point_to_point", "simplex_periodic", "label_sdi", default_bitrate=100_000, max_payload_bytes=4),
            "arinc664_afdx": p("aerospace", "redundant_ethernet", "switched_star", "bandwidth_allocation_gap", "virtual_link", default_bitrate=100_000_000, max_payload_bytes=1_471, native_formats=("pcap", "pcapng")),
            "arinc825": p("aerospace", "differential_pair", "bus", "can_arbitration", "frame_id", default_bitrate=1_000_000, max_payload_bytes=8),
            "mil_std_1553": p("aerospace_defense", "dual_redundant_pair", "bus", "command_response", "terminal_subaddress", default_bitrate=1_000_000, max_payload_bytes=64),
            "spacewire": p("aerospace", "differential_pairs", "point_to_point_network", "wormhole_routing", "path_or_logical", default_bitrate=200_000_000, max_payload_bytes=65_535),
        }
