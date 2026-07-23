"""Marine bus and protocol profiles."""

from physic_lib.Industries.generator_base import BaseTechnologyGenerator, TechnologyProfile


class MarineTechnologyGenerator(BaseTechnologyGenerator):
    domain = "marine"

    def generate(self) -> dict[str, TechnologyProfile]:
        p = self.profile
        return {
            "nmea0183": p("marine", "rs422", "point_to_multipoint", "talker_listener", "sentence_id", default_bitrate=4_800, max_payload_bytes=82),
            "nmea2000": p("marine", "differential_pair", "bus", "can_arbitration", "pgn_and_source", default_bitrate=250_000, max_payload_bytes=223),
            "iec61162": p("marine", "serial_or_ethernet", "mixed", "standard_dependent", "standard_dependent", max_payload_bytes=65_535),
        }
