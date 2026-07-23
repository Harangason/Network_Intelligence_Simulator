"""Energy network protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class EnergyTechnologyGenerator(BaseTechnologyGenerator):
    domain = "energy"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "iec61850": p("energy", "ethernet", "switched", "client_server_or_pubsub", "logical_node", default_bitrate=100_000_000, max_payload_bytes=1_500, native_formats=("pcap", "pcapng")),
            "dnp3": p("energy", "serial_or_ip", "bus_or_network", "master_outstation", "link_address", max_payload_bytes=2_048),
        }
