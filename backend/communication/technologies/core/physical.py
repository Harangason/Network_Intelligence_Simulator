"""Explicit PHY and medium-access models; missing hardware never becomes a default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


class MediumAccessModel(StrEnum):
    BITWISE_PRIORITY = "BITWISE_PRIORITY"
    MASTER_SCHEDULED = "MASTER_SCHEDULED"
    FULL_DUPLEX_SWITCHED = "FULL_DUPLEX_SWITCHED"
    MASTER_SLAVE = "MASTER_SLAVE"
    WIRED_AND_ARBITRATION = "WIRED_AND_ARBITRATION"
    POINT_TO_POINT = "POINT_TO_POINT"
    PLCA = "PLCA"


@dataclass(frozen=True)
class ArbitrationModel:
    id: str
    access: MediumAccessModel
    priority_source: str | None = None
    non_destructive: bool = False
    deterministic: bool = False
    worst_case_delay_model: str | None = None


@dataclass(frozen=True)
class PhysicalLayerProfile:
    id: str
    technology_id: str
    medium_type: str
    required_conductors: tuple[str, ...]
    pair_count: int | None
    differential: bool
    duplex_mode: str
    allowed_topologies: tuple[str, ...]
    termination_count: int | None
    access_model: MediumAccessModel
    arbitration: ArbitrationModel | None = None
    phy_variant: str | None = None


@dataclass(frozen=True)
class PhysicalRealization:
    id: str
    connection_id: str
    technology_id: str
    conductors: tuple[str, ...] | None
    pair_count: int | None
    topology: str | None
    termination_count: int | None
    phy_variant: str | None
    length_m: float | None
    chip_select_count: int | None
    slave_count: int | None
    available_channel_count: int | None
    used_channel_count: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalRealization:
        def integer(name: str) -> int | None:
            value = data.get(name)
            return value if isinstance(value, int) and not isinstance(value, bool) else None

        conductors = data.get("conductors")
        return cls(
            id=str(data.get("id") or ""), connection_id=str(data.get("connection_id") or ""),
            technology_id=str(data.get("technology_id") or data.get("technology") or "").lower().replace("-", "_"),
            conductors=tuple(str(value).upper() for value in conductors) if isinstance(conductors, list) else None,
            pair_count=integer("pair_count"), topology=str(data["topology"]).upper() if data.get("topology") else None,
            termination_count=integer("termination_count"),
            phy_variant=str(data["phy_variant"]).upper() if data.get("phy_variant") else None,
            length_m=float(data["length_m"]) if isinstance(data.get("length_m"), (int, float)) and not isinstance(data["length_m"], bool) else None,
            chip_select_count=integer("chip_select_count"), slave_count=integer("slave_count"),
            available_channel_count=integer("available_channel_count"), used_channel_count=integer("used_channel_count"),
        )


CAN_ARBITRATION = ArbitrationModel("CAN_NON_DESTRUCTIVE", MediumAccessModel.BITWISE_PRIORITY,
                                   priority_source="CAN_IDENTIFIER", non_destructive=True,
                                   deterministic=False, worst_case_delay_model="HIGHER_PRIORITY_INTERFERENCE")

PHYSICAL_PROFILES: dict[str, PhysicalLayerProfile] = {
    "can": PhysicalLayerProfile("CAN_DIFFERENTIAL_PAIR", "can", "TWISTED_PAIR", ("CAN_H", "CAN_L"),
                                1, True, "HALF_DUPLEX", ("BUS", "LINE"), 2,
                                MediumAccessModel.BITWISE_PRIORITY, CAN_ARBITRATION),
    "lin": PhysicalLayerProfile("LIN_SINGLE_WIRE", "lin", "SINGLE_WIRE", ("LIN",),
                                0, False, "HALF_DUPLEX", ("BUS", "LINE"), None,
                                MediumAccessModel.MASTER_SCHEDULED),
    "i2c": PhysicalLayerProfile("I2C_SDA_SCL", "i2c", "PCB_TRACES", ("SDA", "SCL"),
                                0, False, "HALF_DUPLEX", ("BUS", "LINE"), None,
                                MediumAccessModel.WIRED_AND_ARBITRATION),
    "spi": PhysicalLayerProfile("SPI_SYNCHRONOUS", "spi", "PCB_TRACES", ("SCLK", "MOSI", "MISO"),
                                0, False, "FULL_DUPLEX", ("STAR", "POINT_TO_POINT"), None,
                                MediumAccessModel.MASTER_SLAVE),
    "rs485": PhysicalLayerProfile("RS485_DIFFERENTIAL", "rs485", "TWISTED_PAIR", ("A", "B"),
                                  1, True, "HALF_DUPLEX", ("BUS", "LINE"), 2,
                                  MediumAccessModel.MASTER_SLAVE),
    "rs422": PhysicalLayerProfile("RS422_DUAL_DIFFERENTIAL", "rs422", "TWISTED_PAIRS",
                                  ("TX+", "TX-", "RX+", "RX-"), 2, True, "FULL_DUPLEX",
                                  ("POINT_TO_POINT",), None, MediumAccessModel.POINT_TO_POINT),
    "ethernet": PhysicalLayerProfile("ETHERNET_PHY_EXPLICIT", "ethernet", "PHY_DEPENDENT", (), None,
                                     True, "FULL_DUPLEX", ("STAR", "POINT_TO_POINT", "LINE"), None,
                                     MediumAccessModel.FULL_DUPLEX_SWITCHED),
}

PHY_PAIRS = {"10BASE_T1S": 1, "100BASE_T1": 1, "1000BASE_T1": 1,
             "100BASE_TX": 2, "1000BASE_T": 4}

PROFILE_ALIASES = {
    "can_fd": "can", "canopen": "can", "j1939": "can", "nmea2000": "can",
    "modbus_rtu": "rs485", "ethercat": "ethernet", "profinet": "ethernet",
    "modbus_tcp": "ethernet", "ethernet_ip": "ethernet",
    "automotive_ethernet": "ethernet",
}


def physical_profile(technology_id: str) -> PhysicalLayerProfile | None:
    normalized = str(technology_id or "").lower().replace("-", "_")
    return PHYSICAL_PROFILES.get(PROFILE_ALIASES.get(normalized, normalized))


def validate_physical_realization(data: dict[str, Any]) -> dict[str, Any]:
    realization = PhysicalRealization.from_dict(data)
    profile = physical_profile(realization.technology_id)
    findings: list[dict[str, str]] = []

    def finding(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    if profile is None:
        finding("REVIEW", "PHYSICAL_PROFILE_MISSING", "No registered physical profile for this technology.")
    else:
        if realization.conductors is None and profile.required_conductors:
            finding("REVIEW", "PHYSICAL_CONDUCTORS_UNKNOWN", "Conductor assignment is not evidenced.")
        elif realization.conductors is not None:
            missing = set(profile.required_conductors) - set(realization.conductors)
            if missing:
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_MISMATCH", f"Required conductors missing: {', '.join(sorted(missing))}.")
            if len(realization.conductors) != len(set(realization.conductors)):
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_DUPLICATE", "Conductor names must be unique.")
        expected_pairs = PHY_PAIRS.get(realization.phy_variant) if profile.id == "ETHERNET_PHY_EXPLICIT" else profile.pair_count
        if profile.id == "ETHERNET_PHY_EXPLICIT" and not realization.phy_variant:
            finding("REVIEW", "ETHERNET_PHY_UNKNOWN", "Ethernet PHY variant is not evidenced.")
        elif profile.id == "ETHERNET_PHY_EXPLICIT" and expected_pairs is None:
            finding("BLOCKER", "ETHERNET_PHY_UNSUPPORTED", "Ethernet PHY variant is not registered.")
        if expected_pairs is not None:
            if realization.pair_count is None:
                finding("REVIEW", "PHYSICAL_PAIR_COUNT_UNKNOWN", "Physical pair count is not evidenced.")
            elif realization.pair_count != expected_pairs:
                finding("BLOCKER", "PHYSICAL_PAIR_COUNT_MISMATCH", "Pair count is incompatible with the physical profile.")
        allowed_topologies = (("BUS", "LINE") if realization.phy_variant == "10BASE_T1S"
                              and profile.id == "ETHERNET_PHY_EXPLICIT" else profile.allowed_topologies)
        if realization.topology is None:
            finding("REVIEW", "PHYSICAL_TOPOLOGY_UNKNOWN", "Physical topology is not evidenced.")
        elif realization.topology not in allowed_topologies:
            finding("BLOCKER", "PHYSICAL_TOPOLOGY_INVALID", "Topology is incompatible with the physical profile.")
        if profile.termination_count is not None:
            if realization.termination_count is None:
                finding("REVIEW", "PHYSICAL_TERMINATION_UNKNOWN", "Termination count is not evidenced.")
            elif realization.termination_count != profile.termination_count:
                finding("BLOCKER", "PHYSICAL_TERMINATION_INVALID", "Termination count is incompatible with the bus profile.")
        if profile.id == "SPI_SYNCHRONOUS":
            if realization.slave_count is None or realization.chip_select_count is None:
                finding("REVIEW", "SPI_RESOURCE_COUNT_UNKNOWN", "SPI slave and chip-select resources are not fully evidenced.")
            elif realization.chip_select_count < realization.slave_count:
                finding("BLOCKER", "SPI_CHIP_SELECT_EXHAUSTED", "More SPI slaves than available chip selects.")
    if realization.length_m is not None and (not isfinite(realization.length_m) or realization.length_m < 0):
        finding("BLOCKER", "PHYSICAL_LENGTH_INVALID", "Physical length must be a finite non-negative value.")
    if (realization.used_channel_count is not None and realization.available_channel_count is not None and
            realization.used_channel_count > realization.available_channel_count):
        finding("BLOCKER", "PHYSICAL_CHANNEL_LIMIT_EXCEEDED", "Used physical channels exceed hardware capability.")
    return {
        "realization_id": realization.id, "technology_id": realization.technology_id,
        "physical_layer_profile_id": profile.id if profile else None,
        "resolved_medium_access_model": (MediumAccessModel.PLCA.value if realization.phy_variant == "10BASE_T1S"
                                         and profile and profile.id == "ETHERNET_PHY_EXPLICIT" else
                                         profile.access_model.value if profile else None),
        "status": "INVALID" if any(item["severity"] == "BLOCKER" for item in findings) else
                  "REVIEW_REQUIRED" if findings else "VALID",
        "findings": findings,
    }
