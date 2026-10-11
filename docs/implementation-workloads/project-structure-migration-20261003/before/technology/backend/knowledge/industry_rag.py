"""Industry-neutral RAG orchestration for signal-generation evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from .semantic_vocabulary import normalize_engineering_text


@dataclass(frozen=True)
class IndustrySignalRAGProfile:
    key: str
    label: str
    aliases: tuple[str, ...]
    namespace_prefixes: tuple[str, ...]
    tag_rules: tuple[tuple[str, tuple[str, ...]], ...]


NEUTRAL_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("status", ("status", "state", "zustand", "mode")),
    ("counter", ("zaehler", "counter", "count", "bz")),
    ("position", ("pos", "position", "dist", "distanz", "abstand", "distance", "level")),
    ("velocity", ("geschw", "speed", "velocity", "vrel")),
    ("rotational_speed", ("rpm", "drehzahl", "rotational")),
    ("acceleration", ("accel", "beschleunigung")),
    ("angle", ("winkel", "wnkl", "yaw", "pitch", "roll")),
    ("temperature", ("temp", "temperatur", "temperature")),
    ("pressure", ("druck", "pressure")),
    ("voltage", ("spannung", "voltage", "volt")),
    ("current", ("strom", "current", "ampere")),
    ("time", ("zeit", "time", "timestamp", "zeitstempel", "jahr", "monat", "tag", "stunde", "minute", "sekunde")),
    ("identity", ("id", "identifier", "identity", "vin", "serial", "schluessel", "key")),
    ("quality", ("quality", "valid", "gueltig", "existenzmass", "qbit", "std")),
    ("availability", ("available", "availability", "verfuegbar", "verfuegbarkeit", "nichtverfuegbar")),
    ("warning", ("warn", "warning", "warnung")),
    ("fault", ("fehler", "fault", "error", "invalid", "inkonsistenz")),
    ("diagnostic", ("diag", "diagnose", "diagnostic")),
    ("control", ("soll", "target", "setpoint", "freigabe", "enable", "aktiv", "active")),
    ("command", ("cmd", "command", "request", "anforderung")),
    ("payload", ("header", "debug", "payload", "data", "mux")),
    ("object_tracking", ("obj", "objekt", "object", "tracking")),
)


INDUSTRY_RAG_PROFILES: tuple[IndustrySignalRAGProfile, ...] = (
    IndustrySignalRAGProfile(
        key="automotive",
        label="Automotive",
        aliases=("automotive", "vehicle", "fahrzeug", "car"),
        namespace_prefixes=("AB", "BAP", "BV", "BV1", "BVTS", "EA", "ESP", "GNSS", "HCA", "Kamera", "LDW", "LWI", "MO", "PSD", "RDR", "SWA", "TA", "TPA", "UH", "US", "VIN", "VZA", "VZE", "VZM", "WFS", "WLA", "Wischer", "WWSs", "ZAS", "ZV"),
        tag_rules=(
            ("bap", ("bap",)),
            ("body", ("zas", "zv", "wischer", "wiper", "door", "window")),
            ("brake", ("brems", "brake")),
            ("camera", ("kamera", "camera", "bild")),
            ("lane_assistance", ("ldw", "lda", "lane", "spur", "egospur")),
            ("object_perception", ("obj", "objekt", "bv")),
            ("radar", ("rdr", "radar")),
            ("traffic_sign", ("vza", "vze", "verkehrszeichen")),
            ("ultrasonic", ("us", "ultrasonic")),
            ("vehicle_identity", ("vin",)),
        ),
    ),
    IndustrySignalRAGProfile(
        key="industrial_automation",
        label="Industrial Automation",
        aliases=("industrial", "industrial_automation", "manufacturing", "machine", "plc"),
        namespace_prefixes=("PLC", "IO", "DI", "DO", "AI", "AO", "DRV", "AX", "SICK", "FESTO"),
        tag_rules=(
            ("plc", ("plc", "steuerung")),
            ("fieldbus", ("profinet", "profibus", "ethercat", "modbus", "ioline", "io")),
            ("drive", ("drive", "drv", "axis", "achse", "motor")),
            ("safety_io", ("safety", "sicher", "notaus", "estop")),
            ("production", ("cycle", "part", "batch", "werkstueck", "production")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="embedded_systems",
        label="Embedded Systems",
        aliases=("embedded", "embedded_systems", "microcontroller", "mcu"),
        namespace_prefixes=("GPIO", "ADC", "DAC", "PWM", "SPI", "I2C", "UART", "IRQ", "BOOT"),
        tag_rules=(
            ("gpio", ("gpio", "pin")),
            ("analog", ("adc", "dac", "analog")),
            ("serial_bus", ("spi", "i2c", "uart", "rs232", "rs485")),
            ("interrupt", ("irq", "interrupt")),
            ("firmware", ("boot", "reset", "watchdog", "fw")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="aerospace",
        label="Aerospace",
        aliases=("aerospace", "aviation", "avionics", "uav", "satellite", "space"),
        namespace_prefixes=("ARINC", "MIL", "FC", "IMU", "ADIRU", "GNSS", "NAV", "TC", "TM"),
        tag_rules=(
            ("avionics", ("arinc", "mil", "avionics")),
            ("flight_state", ("flight", "airborne", "landed")),
            ("navigation", ("nav", "gnss", "altitude", "heading")),
            ("telemetry", ("telemetry", "tm", "downlink")),
            ("command_link", ("command", "tc", "uplink")),
            ("payload", ("payload", "instrument")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="rail",
        label="Rail",
        aliases=("rail", "railway", "train", "bahn"),
        namespace_prefixes=("ETCS", "TCMS", "MVB", "WTB", "TRDP", "ZUG", "DOOR", "BRK"),
        tag_rules=(
            ("train_control", ("etcs", "tcms", "zug", "train")),
            ("traction", ("traction", "antrieb")),
            ("brake", ("brake", "bremse")),
            ("door", ("door", "tuer")),
            ("wayside", ("balise", "signal", "track")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="marine",
        label="Marine",
        aliases=("marine", "ship", "vessel", "boat", "maritime"),
        namespace_prefixes=("NMEA", "AIS", "GPS", "RUD", "ENG", "NAV"),
        tag_rules=(
            ("navigation", ("nmea", "gps", "nav", "heading", "course")),
            ("vessel_identity", ("ais", "mmsi", "imo")),
            ("propulsion", ("engine", "rpm", "propulsion")),
            ("rudder", ("rudder", "ruder")),
            ("bilge", ("bilge", "pump")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="building_automation",
        label="Building Automation",
        aliases=("building", "building_automation", "hvac", "smart_building"),
        namespace_prefixes=("HVAC", "KNX", "BAC", "ROOM", "AHU", "VAV"),
        tag_rules=(
            ("hvac", ("hvac", "ahu", "vav", "heating", "cooling", "lueftung")),
            ("room", ("room", "raum", "zone")),
            ("occupancy", ("occupancy", "praesenz", "presence")),
            ("lighting", ("light", "licht")),
            ("building_bus", ("knx", "bacnet")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="energy",
        label="Energy",
        aliases=("energy", "grid", "power", "power_grid"),
        namespace_prefixes=("IEC", "IED", "BMS", "PCS", "INV", "GRID", "SOC", "SOH"),
        tag_rules=(
            ("grid", ("grid", "netz", "frequency", "freq")),
            ("breaker", ("breaker", "schalter")),
            ("battery", ("battery", "bms", "soc", "soh")),
            ("inverter", ("inverter", "inv", "pcs")),
            ("power_quality", ("power", "leistung", "quality")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="robotics_ros",
        label="Robotics ROS",
        aliases=("robotics", "robotics_ros", "ros", "ros2", "robot"),
        namespace_prefixes=("ROS", "DDS", "TF", "ODOM", "CMD", "JOINT", "LIDAR", "IMU"),
        tag_rules=(
            ("ros_topic", ("ros", "topic", "dds")),
            ("pose", ("pose", "tf", "odom")),
            ("twist", ("twist", "cmdvel", "velocity")),
            ("joint_state", ("joint", "gelenk")),
            ("perception", ("lidar", "camera", "imu")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="generic_networking",
        label="Generic Networking",
        aliases=("generic_networking", "networking", "network"),
        namespace_prefixes=("ETH", "IP", "TCP", "UDP", "PKT", "FRAME"),
        tag_rules=(
            ("packet", ("packet", "pkt", "frame")),
            ("network_metric", ("latency", "jitter", "throughput", "drop")),
            ("addressing", ("ip", "mac", "address")),
        ),
    ),
    IndustrySignalRAGProfile(
        key="generic",
        label="Generic",
        aliases=("generic", "general", "industry_neutral"),
        namespace_prefixes=(),
        tag_rules=(),
    ),
)


PROFILE_BY_KEY = {profile.key: profile for profile in INDUSTRY_RAG_PROFILES}
PROFILE_ALIASES = {
    alias: profile.key
    for profile in INDUSTRY_RAG_PROFILES
    for alias in (profile.key, profile.label.lower().replace(" ", "_"), *profile.aliases)
}
PROFILE_ALIASES.update(
    {
        "aero": "aerospace",
        "auto": "automotive",
        "can": "automotive",
        "embedded": "embedded_systems",
        "industrial": "industrial_automation",
        "ros": "robotics_ros",
        "ros2": "robotics_ros",
    }
)

SIGNAL_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")
VIN_CHARACTER_PATTERN = re.compile(r"^VIN_(?:[1-9]|1[0-7])$")


def _token(value: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(value or "").lower())).strip("_")


def _has_any(text: str, tokens: list[str], needles: tuple[str, ...]) -> bool:
    compact = text.replace(" ", "")
    token_set = set(tokens)
    return any(
        needle in token_set or (len(needle) > 2 and (needle in text or needle in compact))
        for needle in needles
    )


def signal_name_tokens(name: str) -> list[str]:
    return normalize_engineering_text(name.replace("_", " ")).split()


def signal_namespace(name: str) -> str:
    if match := re.match(r"^(BV_Obj_\d+)", name):
        return match.group(1)
    if match := re.match(r"^(BAP_[A-Za-z0-9]+)", name):
        return match.group(1)
    if match := re.match(r"^([A-Za-z]+\d*)_", name):
        return match.group(1)
    return name


def namespace_pattern(namespace: str) -> str:
    return re.sub(r"\d+", "<n>", namespace)


def _match_tags(rules: tuple[tuple[str, tuple[str, ...]], ...], tokens: list[str], text: str) -> list[str]:
    return [tag for tag, needles in rules if _has_any(text, tokens, needles)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _count_entries(counter: Counter[str], *, limit: int = 24, minimum: int = 1) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
        if count >= minimum
    ]


class IndustryRAGOrchestrator:
    """Routes weak signal evidence into industry partitions and neutral semantics."""

    def __init__(self, profiles: tuple[IndustrySignalRAGProfile, ...] = INDUSTRY_RAG_PROFILES) -> None:
        self.profiles = profiles
        self.by_key = {profile.key: profile for profile in profiles}

    def normalize_industry(self, value: Any) -> str:
        key = _token(value)
        return PROFILE_ALIASES.get(key, key if key in self.by_key else "generic")

    def select_profile(self, name: str, *, industry: Any = None) -> IndustrySignalRAGProfile:
        explicit_key = self.normalize_industry(industry)
        if industry and explicit_key in self.by_key:
            return self.by_key[explicit_key]

        namespace = signal_namespace(name).lower()
        tokens = signal_name_tokens(name)
        text = " ".join(tokens)
        scored: list[tuple[int, str]] = []
        for profile in self.profiles:
            if profile.key == "generic":
                continue
            prefix_score = sum(2 for prefix in profile.namespace_prefixes if namespace == prefix.lower() or namespace.startswith(prefix.lower()))
            tag_score = len(_match_tags(profile.tag_rules, tokens, text))
            if prefix_score or tag_score:
                scored.append((prefix_score + tag_score, profile.key))
        if not scored:
            return self.by_key["generic"]
        score, key = sorted(scored, key=lambda item: (-item[0], item[1]))[0]
        return self.by_key[key] if score >= 1 else self.by_key["generic"]

    def signal_payload(
        self,
        name: str,
        *,
        source_id: str,
        source_line: int,
        industry: Any = None,
        domain: Any = None,
        technology: Any = None,
        source_quality: float = 0.42,
    ) -> dict[str, Any]:
        profile = self.select_profile(name, industry=industry or domain)
        tokens = signal_name_tokens(name)
        text = " ".join(tokens)
        namespace = signal_namespace(name)
        semantic_tags = _dedupe(_match_tags(NEUTRAL_TAG_RULES, tokens, text))
        industry_tags = _dedupe(_match_tags(profile.tag_rules, tokens, text))
        semantic_type = self.semantic_type(name, semantic_tags)
        unit_hint = self.unit_hint(semantic_tags, text)
        encoding_hint = self.encoding_hint(semantic_type, semantic_tags)
        partition = f"signal-generation:{profile.key}"
        resolved_domain = str(domain or profile.key or "generic")
        return {
            "name": name,
            "display_name": name,
            "domain": resolved_domain,
            "industry": profile.key,
            "description": f"Name-only signal evidence for {name}.",
            "namespace": namespace,
            "semantic_type": semantic_type,
            "semantic_tags": semantic_tags,
            "industry_tags": industry_tags,
            "semantic_tokens": tokens,
            "generation_role": "seed_evidence",
            "rag_partition": partition,
            "retrieval_queries": [
                name,
                " ".join([profile.key, namespace, semantic_type, *semantic_tags, *industry_tags]),
                text,
            ],
            "semantic": {
                "semantic_type": semantic_type,
                "meaning": text or name,
                "quantity": next((tag for tag in semantic_tags if tag != "payload"), "UNKNOWN"),
                "unit": unit_hint,
                "system_context": {
                    "industry": profile.key,
                    "namespace": namespace,
                    "tags": semantic_tags,
                    "industry_tags": industry_tags,
                    "rag_partition": partition,
                    "source_granularity": "name_only",
                },
            },
            "data": self.value_domain_hint(semantic_type),
            "configuration": {
                "raw_datatype": None,
                "bit_length": None,
                "signed": encoding_hint["signed"],
                "factor": None,
                "offset": None,
                "endianness": None,
                "encoding_type": encoding_hint["encoding_type"],
                "bit_length_candidates": encoding_hint["bit_length_candidates"],
                "coding_rule": "RAG_NAME_EVIDENCE_REQUIRES_GENERATOR_COMPLETION",
            },
            "quality": {
                "confidence": source_quality,
                "source_quality": source_quality,
                "semantic_complete": False,
                "value_domain_complete": semantic_type == "FLAG",
                "encoding_complete": False,
                "mapping_quality": "name_only",
                "assumptions": ["Signal name was available; DBC/ARXML value tables and bit positions were not provided."],
            },
            "protocol_bindings": [
                {
                    "source_format": "SIGNAL_LIST",
                    "technology": technology,
                    "binding_state": "inferred_context_only",
                }
            ],
            "metadata": {
                "domain": resolved_domain,
                "industry": profile.key,
                "technology": technology,
                "knowledge_level": "L1_IMPORTED",
                "source_quality": source_quality,
                "rag_schema": "rag-signal-generation.v1",
                "rag_partition": partition,
                "namespace": namespace,
                "semantic_type": semantic_type,
                "semantic_tags": semantic_tags,
                "industry_tags": industry_tags,
                "source_id": source_id,
                "source_line": source_line,
            },
        }

    def corpus_profiles(
        self,
        names: list[str],
        *,
        source_id: str,
        industry: Any = None,
        domain: Any = None,
        technology: Any = None,
        source_quality: float = 0.42,
        duplicate_count: int = 0,
        rejected_count: int = 0,
    ) -> list[dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for index, name in enumerate(names, start=1):
            signal = self.signal_payload(
                name,
                source_id=source_id,
                source_line=index,
                industry=industry or domain,
                domain=domain,
                technology=technology,
                source_quality=source_quality,
            )
            buckets[str(signal["industry"])].append(signal)

        profiles = []
        for key in sorted(buckets):
            profile = self.by_key.get(key, self.by_key["generic"])
            signals = buckets[key]
            partition = f"signal-generation:{key}"
            semantic_type_counts = Counter(str(item["semantic_type"]) for item in signals)
            semantic_tag_counts = Counter(tag for item in signals for tag in item["semantic_tags"])
            industry_tag_counts = Counter(tag for item in signals for tag in item["industry_tags"])
            namespace_pattern_counts = Counter(namespace_pattern(str(item["namespace"])) for item in signals)
            top_semantic_tags = list(semantic_tag_counts)
            top_industry_tags = list(industry_tag_counts)
            top_namespaces = [entry["value"] for entry in _count_entries(namespace_pattern_counts, minimum=2)]
            profiles.append(
                {
                    "name": f"{key}_signal_generation_profile",
                    "display_name": f"{profile.label} Signal Generation Profile",
                    "domain": str(domain or key or "generic"),
                    "industry": key,
                    "description": (
                        "Aggregated signal-list profile for generation retrieval. "
                        "Raw signal names are not persisted."
                    ),
                    "profile_kind": "signal_generation_corpus",
                    "generation_role": "corpus_profile",
                    "rag_partition": partition,
                    "observed_signal_count": len(signals),
                    "duplicate_count": int(duplicate_count),
                    "rejected_count": int(rejected_count),
                    "raw_signal_names_persisted": False,
                    "semantic_type_counts": dict(semantic_type_counts),
                    "semantic_tag_counts": _count_entries(semantic_tag_counts),
                    "industry_tag_counts": _count_entries(industry_tag_counts),
                    "namespace_pattern_counts": _count_entries(namespace_pattern_counts, minimum=2),
                    "retrieval_queries": [
                        " ".join([partition, profile.label, *top_semantic_tags, *top_industry_tags]),
                        " ".join(top_namespaces),
                    ],
                    "generator_contract": {
                        "may_use": [
                            "industry partition",
                            "semantic distribution",
                            "namespace patterns",
                            "tag distributions",
                        ],
                        "must_not_use": ["raw signal name lookup", "implicit approval"],
                        "must_complete": [
                            "signal names",
                            "message assignment",
                            "start bits",
                            "bit lengths",
                            "byte order",
                            "value domains",
                            "protocol bindings",
                        ],
                    },
                    "quality": {
                        "confidence": source_quality,
                        "source_quality": source_quality,
                        "semantic_complete": False,
                        "value_domain_complete": False,
                        "encoding_complete": False,
                        "mapping_quality": "aggregate_profile",
                        "assumptions": [
                            "Only aggregate signal-list patterns are retained; individual names were discarded."
                        ],
                    },
                    "metadata": {
                        "domain": str(domain or key or "generic"),
                        "industry": key,
                        "technology": technology,
                        "knowledge_level": "L1_IMPORTED",
                        "source_quality": source_quality,
                        "rag_schema": "rag-signal-generation.v1",
                        "rag_partition": partition,
                        "semantic_tags": top_semantic_tags,
                        "industry_tags": top_industry_tags,
                        "source_id": source_id,
                        "raw_signal_names_persisted": False,
                    },
                }
            )
        return profiles

    @staticmethod
    def semantic_type(name: str, semantic_tags: list[str]) -> str:
        tag_set = set(semantic_tags)
        tokens = signal_name_tokens(name)
        text = " ".join(tokens)
        physical_tags = {"position", "velocity", "rotational_speed", "acceleration", "angle", "temperature", "pressure", "voltage", "current", "time", "quality"}
        if VIN_CHARACTER_PATTERN.match(name):
            return "STRING"
        if "counter" in tag_set:
            return "COUNTER"
        if tag_set & physical_tags:
            return "NUMERIC"
        if "payload" in tag_set:
            return "BYTE_ARRAY" if _has_any(text, tokens, ("header", "debug", "payload")) else "ENUM"
        if "status" in tag_set or _has_any(text, tokens, ("klasse", "typ", "type", "ea")):
            return "STATE"
        if tag_set & {"warning", "fault", "availability"} or _has_any(text, tokens, ("valid", "aktiv", "enable", "freigabe", "bremst", "fahrberecht", "blindheit")):
            return "FLAG"
        if "identity" in tag_set and name.startswith("VIN_"):
            return "STRING"
        return "UNKNOWN"

    @staticmethod
    def unit_hint(semantic_tags: list[str], text: str) -> str | None:
        tag_set = set(semantic_tags)
        if "time" in tag_set:
            if any(token in text for token in ("jahr", "monat", "tag", "stunde", "minute", "sekunde")):
                return "calendar_field"
            return "ms"
        if "position" in tag_set:
            return "m"
        if "velocity" in tag_set:
            return "m/s"
        if "rotational_speed" in tag_set:
            return "rpm"
        if "acceleration" in tag_set:
            return "m/s2"
        if "angle" in tag_set:
            return "deg"
        if "temperature" in tag_set:
            return "degC"
        if "pressure" in tag_set:
            return "bar"
        if "voltage" in tag_set:
            return "V"
        if "current" in tag_set:
            return "A"
        if "quality" in tag_set and any(token in text for token in ("existenzmass", "quality")):
            return "%"
        return None

    @staticmethod
    def encoding_hint(semantic_type: str, semantic_tags: list[str]) -> dict[str, Any]:
        tag_set = set(semantic_tags)
        if semantic_type == "FLAG":
            return {"bit_length_candidates": [1], "encoding_type": "coded", "signed": False}
        if semantic_type == "COUNTER":
            return {"bit_length_candidates": [4, 8, 16], "encoding_type": "counter", "signed": False}
        if semantic_type in {"STATE", "ENUM"}:
            return {"bit_length_candidates": [2, 4, 8], "encoding_type": "coded", "signed": False}
        if semantic_type == "STRING":
            return {"bit_length_candidates": [8], "encoding_type": "ascii_char", "signed": False}
        if semantic_type == "BYTE_ARRAY":
            return {"bit_length_candidates": [8, 16, 32, 64], "encoding_type": "opaque_payload", "signed": False}
        if tag_set & {"angle", "velocity", "position", "temperature", "pressure", "current", "acceleration"}:
            return {"bit_length_candidates": [12, 16, 32], "encoding_type": "linear", "signed": True}
        if "voltage" in tag_set or "rotational_speed" in tag_set or "quality" in tag_set:
            return {"bit_length_candidates": [8, 16, 32], "encoding_type": "linear", "signed": False}
        return {"bit_length_candidates": [8, 16, 32], "encoding_type": "unknown", "signed": None}

    @staticmethod
    def value_domain_hint(semantic_type: str) -> dict[str, Any]:
        if semantic_type == "FLAG":
            return {
                "allowed_values": [False, True],
                "enum_values": {"FALSE": 0, "TRUE": 1},
                "reserved_values": [],
                "invalid_values": [],
                "default_value": False,
            }
        if semantic_type == "COUNTER":
            return {
                "minimum": 0,
                "maximum": None,
                "resolution": 1,
                "allowed_values": [],
                "enum_values": {},
                "reserved_values": [],
                "invalid_values": [],
                "default_value": 0,
            }
        if semantic_type in {"STATE", "ENUM"}:
            return {
                "allowed_values": [],
                "enum_values": {},
                "reserved_values": [],
                "invalid_values": ["SNA", "INVALID", "NOT_AVAILABLE"],
                "default_value": None,
            }
        if semantic_type == "STRING":
            return {
                "allowed_values": [],
                "enum_values": {},
                "reserved_values": [],
                "invalid_values": [],
                "default_value": "",
            }
        return {
            "minimum": None,
            "maximum": None,
            "resolution": None,
            "allowed_values": [],
            "enum_values": {},
            "reserved_values": [],
            "invalid_values": [],
            "default_value": None,
        }
