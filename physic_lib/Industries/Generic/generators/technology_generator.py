"""Generic Ethernet, network and transport profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class GenericNetworkTechnologyGenerator(BaseTechnologyGenerator):
    domain = "generic_networking"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "ethernet": p("general", "copper_or_fiber", "switched_star", "full_duplex", "mac", default_bitrate=1_000_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
            "ipv4": p("general", "network_layer", "routed", "best_effort", "ipv4", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
            "ipv6": p("general", "network_layer", "routed", "best_effort", "ipv6", max_payload_bytes=65_575, native_formats=("pcap", "pcapng"), kind="protocol"),
            "udp": p("general", "transport_layer", "routed", "datagram", "port", max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
            "tcp": p("general", "transport_layer", "routed", "stream", "port", max_payload_bytes=65_535, native_formats=("pcap", "pcapng"), kind="protocol"),
        }
