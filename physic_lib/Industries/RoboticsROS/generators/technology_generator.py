"""Robotics middleware protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class RoboticsTechnologyGenerator(BaseTechnologyGenerator):
    domain = "robotics_ros"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "dds_rtps": p("robotics", "ethernet_or_ip", "switched_or_routed", "data_centric_pubsub", "domain_topic_guid", max_payload_bytes=65_507, native_formats=("pcap", "pcapng"), kind="protocol"),
            "ros2": p("robotics", "dds_or_custom_transport", "distributed_graph", "pubsub_service_action", "namespace_topic_node", max_payload_bytes=65_507, kind="protocol"),
        }
