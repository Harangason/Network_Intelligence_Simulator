#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realistisches Communication Trace Tool

Erzeugt:
- CAN/CAN-FD/CAN-XL BLF Trace mit realen Sender-/Empfänger-Dialogen
- Ethernet PCAP/PCAPNG mit SOME/IP-ähnlicher Kommunikation
- zyklische Datenbotschaften plus passende Empfangsantworten
- je 25 Signalen logisch pro Botschaft
- Classic CAN, CAN-FD, CAN-XL-Profil und Ethernet-Unterstützung
- DBC-Datei passend zum Trace
- Rolling/Alive Counter
- CRC-8 über Nutzdaten mit Prüfung im Empfänger
- ACK/NACK Response, z.B. LIDAR_FRONT sendet Daten und ADAS_DOMAIN antwortet
- Gateway-Weiterleitung auf zweiten Kanal
- Fehler-/Störszenarien: Dropouts, Jitter, Timeout-Lücken, Bus-Off-Pause,
  DLC-Fehler, Counter-Fehler, CRC-Fehler, Timing-Violations
- Restbussimulation aus einer neutralen Standalone-JSON-Konfiguration

Installation:
    py -m pip install python-can

Beispiel:
    py generate_realistic_communication_tool.py --list-technologies
    py generate_realistic_communication_tool.py --technology arinc429 --duration 5 --nodes 3
    py generate_realistic_communication_tool.py --technology modbus_tcp --cycle-ms 20 --payload-bytes 64
    py generate_realistic_communication_tool.py --duration 60 --out realistic_can_trace.blf
    py generate_realistic_communication_tool.py --formats all --out-dir generated_trace_package
    py generate_realistic_communication_tool.py --simulation-mode restbus --formats blf,dbc,json --out-dir generated_restbus
    py generate_realistic_communication_tool.py --write-config-template simulation_config.json
    py generate_realistic_communication_tool.py --config simulation_config.json

Hinweis:
- BLF ist ein Vector-nahes Binärformat. python-can kann BLF schreiben/lesen.
- DBC enthält bei Classic CAN nur die ersten Signale, die in 8 Byte passen.
  Für 25 Signale pro Botschaft nutzt dieser Generator CAN-FD als realistischere Option.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import can

from bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY
from filter_system import create_filter_bank, profile_from_request, summarize_filter_banks
from hardware_profile import hardware_profile_summary, normalize_hardware_config, validate_hardware_profile
from signal_suggestions import suggest_signal_gaps
from standalone_cli import InteractiveStandaloneCli, StandaloneCliRunner, options_from_namespace
from trace_realism import (
    contains_external_signal_records,
    external_signal_records,
    physical_raw_value,
    signal_specs_for_message,
    trace_quality_summary,
)

LIB_ROOT = Path("physic_lib")
TRACE_ROOT = Path("traces")

try:
    CanMessage = can.Message
    BLFReader = can.BLFReader
    BLFWriter = can.BLFWriter
except AttributeError:
    from can.message import Message as CanMessage
    from can.io.blf import BLFReader, BLFWriter


class ProgressBar:
    def __init__(self, enabled: bool = True, width: int = 32) -> None:
        self.enabled = enabled
        self.width = width
        self.last_len = 0

    def update(self, percent: int, message: str) -> None:
        if not self.enabled:
            return
        percent = max(0, min(100, int(percent)))
        filled = round(self.width * percent / 100)
        bar = "#" * filled + "-" * (self.width - filled)
        text = f"\r[{bar}] {message} {percent}%"
        padding = " " * max(0, self.last_len - len(text))
        print(text + padding, end="", flush=True)
        self.last_len = len(text)
        if percent >= 100:
            print()
            self.last_len = 0

    def line(self) -> None:
        if self.enabled and self.last_len:
            print()
            self.last_len = 0


# -----------------------------
# Datenmodell
# -----------------------------

@dataclass
class SignalDef:
    name: str
    start_bit: int
    length: int
    factor: float
    offset: float
    minimum: int
    maximum: int
    unit: str
    kind: str  # normal | counter | crc | mux | diag


@dataclass
class MessageDef:
    name: str
    frame_id: int
    sender: str
    receivers: List[str]
    cycle_ms: int
    channel: int
    dlc: int
    is_fd: bool
    bus_type: str = "classic"  # classic | fd | xl
    signals: List[SignalDef] = field(default_factory=list)
    gateway_to_channel: int | None = None
    kind: str = "data"  # data | response
    response_for: int | None = None


@dataclass
class RestbusParticipant:
    name: str
    role: str
    channel: int
    cycle_ms: int
    provided_services: List[str] = field(default_factory=list)
    consumed_services: List[str] = field(default_factory=list)
    gateway_to_channel: int | None = None
    wakeup_time_s: float = 0.0
    health: str = "nominal"
    signals: List[Dict[str, Any]] = field(default_factory=list)


ROUTE_INFO_START_BYTE = 20
ROUTE_INFO_LENGTH = 44
COMMON_NOMINAL_BITRATES = {
    "a": 10_000,
    "b": 20_000,
    "c": 33_333,
    "d": 50_000,
    "e": 83_333,
    "f": 100_000,
    "g": 125_000,
    "h": 250_000,
    "i": 500_000,
    "j": 800_000,
    "k": 1_000_000,
}
CAN_FD_DATA_BITRATES = {
    "a": 500_000,
    "b": 1_000_000,
    "c": 2_000_000,
    "d": 4_000_000,
    "e": 5_000_000,
    "f": 8_000_000,
    "g": 10_000_000,
}
CAN_XL_DATA_BITRATES = {
    "a": 2_000_000,
    "b": 4_000_000,
    "c": 5_000_000,
    "d": 8_000_000,
    "e": 10_000_000,
    "f": 12_500_000,
    "g": 16_000_000,
    "h": 20_000_000,
}
ETHERNET_BITRATES = {
    "a": 10_000_000,
    "b": 100_000_000,
    "c": 1_000_000_000,
    "d": 2_500_000_000,
}

DEFAULT_ROUTING_ROWS = [
    {"sender": "LIDAR_FRONT", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 0, "gateway_to_channel": 1, "frame_id": 0x100, "name": "LIDAR_OBJECT_LIST"},
    {"sender": "CAMERA_FRONT_WIDE", "receiver": "ADAS_DOMAIN", "cycle_ms": 33, "channel": 1, "gateway_to_channel": "", "frame_id": 0x101, "name": "CAMERA_LANE_MODEL"},
    {"sender": "RADAR_FRONT_LONG_RANGE", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 2, "gateway_to_channel": "", "frame_id": 0x102, "name": "RADAR_TARGET_LIST"},
    {"sender": "RADAR_REAR_CROSS_TRAFFIC", "receiver": "ADAS_DOMAIN", "cycle_ms": 50, "channel": 3, "gateway_to_channel": "", "frame_id": 0x103, "name": "REAR_CROSS_TRAFFIC"},
    {"sender": "ULTRASONIC_LEFT_CLUSTER", "receiver": "PARK_ASSIST", "cycle_ms": 40, "channel": 4, "gateway_to_channel": "", "frame_id": 0x104, "name": "ULTRASONIC_LEFT_DISTANCE"},
    {"sender": "ULTRASONIC_RIGHT_CLUSTER", "receiver": "PARK_ASSIST", "cycle_ms": 40, "channel": 5, "gateway_to_channel": "", "frame_id": 0x105, "name": "ULTRASONIC_RIGHT_DISTANCE"},
    {"sender": "IMU_YAW_RATE_SENSOR", "receiver": "ADAS_DOMAIN", "cycle_ms": 10, "channel": 6, "gateway_to_channel": "", "frame_id": 0x106, "name": "IMU_DYNAMICS"},
    {"sender": "WHEEL_SPEED_FRONT_LEFT", "receiver": "BRAKE_CONTROLLER", "cycle_ms": 10, "channel": 7, "gateway_to_channel": "", "frame_id": 0x107, "name": "WHEEL_SPEED_FL"},
    {"sender": "BRAKE_CONTROLLER", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 8, "gateway_to_channel": "", "frame_id": 0x108, "name": "BRAKE_STATUS"},
    {"sender": "ADAS_DOMAIN", "receiver": "VEHICLE_MOTION_CONTROLLER", "cycle_ms": 20, "channel": 9, "gateway_to_channel": "", "frame_id": 0x109, "name": "ADAS_MOTION_REQUEST"},
]

DEFAULT_RESTBUS_PARTICIPANTS = [
    {
        "name": "ADAS_DOMAIN",
        "role": "domain_controller",
        "channel": 0,
        "cycle_ms": 20,
        "provided_services": ["OBJECT_FUSION", "TRAJECTORY_PLAN", "MOTION_REQUEST"],
        "consumed_services": ["OBJECT_LIST", "LANE_MODEL", "VEHICLE_DYNAMICS", "BRAKE_STATUS"],
        "gateway_to_channel": 1,
    },
    {
        "name": "LIDAR_FRONT",
        "role": "lidar_sensor",
        "channel": 0,
        "cycle_ms": 20,
        "provided_services": ["OBJECT_LIST"],
        "consumed_services": ["SYNC_TIME"],
    },
    {
        "name": "CAMERA_FRONT_WIDE",
        "role": "camera_sensor",
        "channel": 1,
        "cycle_ms": 33,
        "provided_services": ["LANE_MODEL", "OBJECT_LIST"],
        "consumed_services": ["SYNC_TIME"],
    },
    {
        "name": "AMBIENT_TEMP_SENSOR",
        "role": "temperature_sensor",
        "channel": 3,
        "cycle_ms": 100,
        "provided_services": ["AMBIENT_TEMPERATURE"],
        "consumed_services": ["SYNC_TIME"],
    },
    {
        "name": "ADAS_ECU_TEMP_SENSOR",
        "role": "temperature_sensor",
        "channel": 3,
        "cycle_ms": 100,
        "provided_services": ["ECU_TEMPERATURE"],
        "consumed_services": ["SYNC_TIME"],
    },
    {
        "name": "RADAR_FRONT_LONG_RANGE",
        "role": "radar_sensor",
        "channel": 0,
        "cycle_ms": 20,
        "provided_services": ["OBJECT_LIST"],
        "consumed_services": ["SYNC_TIME"],
    },
    {
        "name": "BRAKE_CONTROLLER",
        "role": "actuator_controller",
        "channel": 2,
        "cycle_ms": 10,
        "provided_services": ["BRAKE_STATUS"],
        "consumed_services": ["MOTION_REQUEST"],
    },
    {
        "name": "VEHICLE_MOTION_CONTROLLER",
        "role": "actuator_controller",
        "channel": 2,
        "cycle_ms": 20,
        "provided_services": ["VEHICLE_DYNAMICS"],
        "consumed_services": ["TRAJECTORY_PLAN"],
    },
    {
        "name": "CENTRAL_GATEWAY",
        "role": "gateway",
        "channel": 0,
        "cycle_ms": 50,
        "provided_services": ["ROUTING_STATUS", "SYNC_TIME", "AMBIENT_TEMPERATURE", "ECU_TEMPERATURE"],
        "consumed_services": ["DIAGNOSTIC_REQUEST", "AMBIENT_TEMPERATURE", "ECU_TEMPERATURE"],
        "gateway_to_channel": 2,
    },
    {
        "name": "DIAG_TESTER",
        "role": "tester",
        "channel": 3,
        "cycle_ms": 100,
        "provided_services": ["DIAGNOSTIC_REQUEST"],
        "consumed_services": ["ROUTING_STATUS", "BRAKE_STATUS"],
    },
]

ROLE_CYCLE_FALLBACK_MS = {
    "lidar_sensor": 20,
    "camera_sensor": 33,
    "radar_sensor": 20,
    "ultrasonic_sensor": 40,
    "imu_sensor": 10,
    "wheel_speed_sensor": 10,
    "temperature_sensor": 100,
    "sensor": 20,
    "domain_controller": 20,
    "actuator_controller": 20,
    "gateway": 50,
    "tester": 100,
    "ecu": 20,
}


# -----------------------------
# CRC / Packing
# -----------------------------

def crc8_autosar(data: bytes, start_value: int = 0xFF, final_xor: int = 0xFF) -> int:
    """CRC-8 SAE J1850/AUTOSAR-ähnlich: poly 0x1D."""
    crc = start_value
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x1D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ final_xor


def set_unsigned_le(payload: bytearray, start_bit: int, length: int, value: int) -> None:
    """Setzt ein unsigned little-endian / Intel Signal bitweise."""
    max_value = (1 << length) - 1
    value = int(value) & max_value
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        bit_index = absolute_bit % 8
        if value & (1 << bit):
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def get_unsigned_le(payload: bytes | bytearray, start_bit: int, length: int) -> int:
    """Liest ein unsigned little-endian / Intel Signal bitweise."""
    value = 0
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        if byte_index >= len(payload):
            break
        bit_index = absolute_bit % 8
        if payload[byte_index] & (1 << bit_index):
            value |= 1 << bit
    return value


def verify_payload_crc(payload: bytes) -> bool:
    if len(payload) < 2:
        return False
    return payload[0] == crc8_autosar(payload[1:])


def route_label(sender: str, receiver: str) -> str:
    return f"{sender} -> {receiver}"


def triangle_wave(t_s: float, period_s: float, minimum: int, maximum: int) -> int:
    if period_s <= 0:
        return minimum
    phase = (t_s % period_s) / period_s
    if phase < 0.5:
        y = phase * 2.0
    else:
        y = (1.0 - phase) * 2.0
    return int(minimum + y * (maximum - minimum))


def safe_identifier(value: str, fallback: str = "NODE") -> str:
    cleaned = re.sub(r"\W+", "_", str(value).strip()).strip("_").upper()
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}"
    return cleaned


def parse_optional_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(text, 0)


def normalized_routing_row(row: Dict[str, object], index: int, channel_count: int) -> Dict[str, object]:
    sender_raw = row.get("sender") or row.get("source") or row.get("src") or f"ECU_{index:02d}"
    receiver_raw = row.get("receiver") or row.get("destination") or row.get("dst") or row.get("target") or "ADAS_DOMAIN"
    sender = safe_identifier(str(sender_raw), "ECU")
    receiver = safe_identifier(str(receiver_raw), "ECU")
    cycle_ms = parse_optional_int(row.get("cycle_ms") or row.get("cycle") or row.get("period_ms"), 20)
    channel = parse_optional_int(row.get("channel"), index % channel_count)
    channel = max(0, min(channel_count - 1, channel if channel is not None else index % channel_count))
    gateway_to_channel = parse_optional_int(row.get("gateway_to_channel") or row.get("gateway") or row.get("gw_channel"), None)
    if gateway_to_channel is not None:
        gateway_to_channel = max(0, min(channel_count - 1, gateway_to_channel))
    frame_id = parse_optional_int(row.get("frame_id") or row.get("id") or row.get("can_id"), 0x100 + index)
    name_raw = row.get("name") or row.get("message") or row.get("message_name") or f"{sender}_TO_{receiver}"
    normalized = {
        "sender": sender,
        "receiver": receiver,
        "cycle_ms": cycle_ms if cycle_ms and cycle_ms > 0 else 20,
        "channel": channel,
        "gateway_to_channel": gateway_to_channel,
        "frame_id": frame_id if frame_id is not None else 0x100 + index,
        "name": safe_identifier(str(name_raw), "MSG"),
    }
    route_signals = external_signal_records(row.get("signals") or row.get("signal_definitions") or row.get("message_signals"))
    if route_signals:
        normalized["signals"] = route_signals
        normalized["signal_source"] = str(row.get("signal_source") or "external")
    return normalized


def load_routing_table(path: Path, channel_count: int) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Routing table is empty: {path}")
    return [normalized_routing_row(row, index, channel_count) for index, row in enumerate(rows)]


def write_routing_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["name", "sender", "receiver", "cycle_ms", "channel", "gateway_to_channel", "frame_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in DEFAULT_ROUTING_ROWS:
            output_row = dict(row)
            output_row["frame_id"] = f"0x{int(output_row['frame_id']):X}"
            writer.writerow(output_row)


def clamp_channel(value: object, channel_count: int, fallback: int = 0) -> int:
    parsed = parse_optional_int(value, fallback)
    channel = fallback if parsed is None else parsed
    return max(0, min(max(1, channel_count) - 1, channel))


def normalize_service_names(values: object) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [part.strip() for part in values.split(",")]
    elif isinstance(values, list):
        raw_values = [str(part).strip() for part in values]
    else:
        raw_values = [str(values).strip()]
    services: List[str] = []
    for raw in raw_values:
        if not raw:
            continue
        service = safe_identifier(raw, "SERVICE")
        if service not in services:
            services.append(service)
    return services


def normalize_restbus_participant(row: Dict[str, object], index: int, channel_count: int) -> RestbusParticipant:
    role = safe_identifier(str(row.get("role") or row.get("type") or "ecu"), "ROLE").lower()
    cycle_default = ROLE_CYCLE_FALLBACK_MS.get(role, ROLE_CYCLE_FALLBACK_MS["ecu"])
    cycle_ms = parse_optional_int(row.get("cycle_ms") or row.get("cycle") or row.get("period_ms"), cycle_default)
    gateway_to_channel = parse_optional_int(row.get("gateway_to_channel") or row.get("gateway") or row.get("gw_channel"), None)
    if gateway_to_channel is not None:
        gateway_to_channel = clamp_channel(gateway_to_channel, channel_count)
    raw_signals = row.get("signals")
    provided_alias = None if contains_external_signal_records(raw_signals) else raw_signals
    return RestbusParticipant(
        name=safe_identifier(str(row.get("name") or row.get("id") or f"ECU_{index:02d}"), "ECU"),
        role=role,
        channel=clamp_channel(row.get("channel"), channel_count, index % max(1, channel_count)),
        cycle_ms=cycle_ms if cycle_ms and cycle_ms > 0 else cycle_default,
        provided_services=normalize_service_names(row.get("provided_services") or row.get("provides") or provided_alias),
        consumed_services=normalize_service_names(row.get("consumed_services") or row.get("consumes")),
        gateway_to_channel=gateway_to_channel,
        wakeup_time_s=float(row.get("wakeup_time_s") or row.get("wakeup_s") or 0.0),
        health=str(row.get("health") or "nominal").strip().lower(),
        signals=external_signal_records(raw_signals or row.get("signal_definitions") or row.get("message_signals")),
    )


def default_restbus_participants(channel_count: int) -> List[RestbusParticipant]:
    return [
        normalize_restbus_participant(row, index, channel_count)
        for index, row in enumerate(DEFAULT_RESTBUS_PARTICIPANTS)
    ]


def restbus_participants_from_request(request: Dict[str, Any], channel_count: int) -> List[RestbusParticipant]:
    raw_participants = request.get("participants") or request.get("nodes") or request.get("ecus")
    if raw_participants is None:
        return default_restbus_participants(channel_count)
    if not isinstance(raw_participants, list):
        raise ValueError("Configuration field 'participants' must be a list.")
    participants = [
        normalize_restbus_participant(dict(row), index, channel_count)
        for index, row in enumerate(raw_participants)
    ]
    if not participants:
        raise ValueError("Restbus configuration must contain at least one participant.")
    return participants


def load_simulation_config(path: Path) -> Dict[str, Any]:
    path = resolve_library_request_path(path)
    request = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(request, dict):
        raise ValueError(f"Simulation configuration must be a JSON object: {path}")
    return request


def resolve_library_request_path(path: Path) -> Path:
    path = Path(path)
    if path.exists():
        return path
    if path.is_absolute() or path.parent != Path("."):
        return path
    library_root = LIB_ROOT
    if not library_root.exists():
        return path
    matches = [
        item
        for item in library_root.rglob(path.name)
        if item.is_file() and item.name == path.name
    ]
    if len(matches) == 1:
        return matches[0]
    return path


def write_simulation_config_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "schema": "communication-simulator.simulation-config.v1",
        "simulation_mode": "restbus",
        "output_dir": "generated_restbus_simulation",
        "formats": "blf,dbc,json,csv",
        "duration_s": 10.0,
        "bus_type": "fd",
        "channels": 4,
        "messages": None,
        "nominal_bitrate": 500000,
        "data_bitrate": 2000000,
        "seed": 42,
        "participants": DEFAULT_RESTBUS_PARTICIPANTS,
    }
    path.write_text(json.dumps(request, indent=2), encoding="utf-8")


def participant_service_pairs(participants: List[RestbusParticipant]) -> List[Tuple[RestbusParticipant, RestbusParticipant, str]]:
    pairs: List[Tuple[RestbusParticipant, RestbusParticipant, str]] = []
    active_participants = [
        participant for participant in participants
        if participant.health not in {"offline", "disabled", "not_available"}
    ]
    if not active_participants:
        return []
    for sender in active_participants:
        for service in sender.provided_services:
            consumers = [
                receiver for receiver in active_participants
                if receiver.name != sender.name and service in receiver.consumed_services
            ]
            for receiver in consumers:
                pairs.append((sender, receiver, service))

    if pairs:
        return pairs

    controllers = [p for p in active_participants if "controller" in p.role or "domain" in p.role]
    sensors = [p for p in active_participants if "sensor" in p.role or p.role in {"lidar_sensor", "camera_sensor", "radar_sensor"}]
    actuators = [p for p in active_participants if "actuator" in p.role]
    gateway = next((p for p in active_participants if "gateway" in p.role), None)
    fallback_controller = controllers[0] if controllers else (gateway or active_participants[0])

    for sensor in sensors:
        if sensor.name != fallback_controller.name:
            pairs.append((sensor, fallback_controller, "SENSOR_DATA"))
    for controller in controllers:
        for actuator in actuators:
            if controller.name != actuator.name:
                pairs.append((controller, actuator, "CONTROL_COMMAND"))
    if gateway is not None:
        for participant in active_participants:
            if participant.name != gateway.name:
                pairs.append((gateway, participant, "NETWORK_MANAGEMENT"))
    if not pairs and len(active_participants) > 1:
        for index, sender in enumerate(active_participants):
            receiver = active_participants[(index + 1) % len(active_participants)]
            if sender.name != receiver.name:
                pairs.append((sender, receiver, "RESTBUS_SIGNAL"))
    return pairs


def route_cycle_ms(sender: RestbusParticipant, receiver: RestbusParticipant) -> int:
    cycle_ms = min(sender.cycle_ms, receiver.cycle_ms) if receiver.cycle_ms else sender.cycle_ms
    if sender.health in {"degraded", "faulty"} or receiver.health in {"degraded", "faulty"}:
        cycle_ms *= 2
    return max(1, cycle_ms)


def build_restbus_routing_rows(
    participants: List[RestbusParticipant],
    channel_count: int,
    max_routes: int | None = None,
    base_frame_id: int = 0x180,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for index, (sender, receiver, service) in enumerate(participant_service_pairs(participants)):
        if max_routes is not None and len(rows) >= max_routes:
            break
        route_name = safe_identifier(f"{sender.name}_{service}_TO_{receiver.name}", "RESTBUS_MSG")
        gateway_to_channel = sender.gateway_to_channel
        if gateway_to_channel is None and sender.channel != receiver.channel:
            gateway_to_channel = receiver.channel
        rows.append(
            normalized_routing_row(
                {
                    "name": route_name,
                    "sender": sender.name,
                    "receiver": receiver.name,
                    "cycle_ms": route_cycle_ms(sender, receiver),
                    "channel": sender.channel,
                    "gateway_to_channel": gateway_to_channel,
                    "frame_id": base_frame_id + index,
                    "signals": sender.signals,
                    "signal_source": "external" if sender.signals else "generated",
                },
                index,
                channel_count,
            )
        )

    if not rows:
        raise ValueError("Restbus simulation needs at least two participants or one valid service relation.")
    return rows


def restbus_interface_summary(participants: List[RestbusParticipant], routing_rows: List[Dict[str, object]]) -> Dict[str, object]:
    return {
        "participants": [
            {
                "name": participant.name,
                "role": participant.role,
                "channel": participant.channel,
                "cycle_ms": participant.cycle_ms,
                "provided_services": participant.provided_services,
                "consumed_services": participant.consumed_services,
                "gateway_to_channel": participant.gateway_to_channel,
                "wakeup_time_s": participant.wakeup_time_s,
                "health": participant.health,
                "signals": participant.signals,
            }
            for participant in participants
        ],
        "routes": [
            {
                "name": row["name"],
                "sender": row["sender"],
                "receiver": row["receiver"],
                "cycle_ms": row["cycle_ms"],
                "channel": row["channel"],
                "gateway_to_channel": row["gateway_to_channel"],
                "frame_id": f"0x{int(row['frame_id']):X}",
                "signal_source": row.get("signal_source"),
                "signals": row.get("signals"),
            }
            for row in routing_rows
        ],
    }


def apply_simulation_config_to_args(args: argparse.Namespace, request: Dict[str, Any]) -> None:
    mapping = {
        "output_dir": "out_dir",
        "out_dir": "out_dir",
        "formats": "formats",
        "duration_s": "duration",
        "duration": "duration",
        "messages": "messages",
        "seed": "seed",
        "channels": "channels",
        "bus_type": "bus",
        "bus": "bus",
        "nominal_bitrate": "nominal_bitrate",
        "fd_bitrate": "fd_bitrate",
        "data_bitrate": "fd_bitrate",
        "xl_data_bitrate": "xl_data_bitrate",
        "eth_bitrate": "eth_bitrate",
        "eth_bitrates": "eth_bitrates",
        "eth_messages": "eth_messages",
        "simulation_mode": "simulation_mode",
        "interface_out": "interface_out",
    }
    for source, target in mapping.items():
        if source in request and request[source] is not None:
            setattr(args, target, request[source])
    if isinstance(request.get("scenario"), dict):
        args.scenario = request["scenario"]
    args.filter_system = profile_from_request(request)
    args.hardware = normalize_hardware_config(request)
    args.hardware_summary = hardware_profile_summary(args.hardware)
    args.hardware_validation = validate_hardware_profile(args.hardware)
    for attr in ["messages", "seed", "channels", "nominal_bitrate", "fd_bitrate", "xl_data_bitrate", "eth_bitrate", "eth_messages"]:
        value = getattr(args, attr, None)
        if value is not None:
            setattr(args, attr, int(value))
    if getattr(args, "duration", None) is not None:
        args.duration = float(args.duration)
    if getattr(args, "interface_out", None) is not None and not isinstance(args.interface_out, Path):
        args.interface_out = Path(str(args.interface_out))


def write_simulation_interface(
    path: Path,
    *,
    simulation_mode: str,
    written: List[Path],
    warnings: List[str],
    duration_s: float,
    bus_type: str,
    channel_count: int,
    nominal_bitrate: int,
    data_bitrate: int | None,
    routing_rows: List[Dict[str, object]] | None,
    restbus_summary: Dict[str, object] | None,
    filter_summary: Dict[str, object] | None = None,
    signal_suggestions: Dict[str, object] | None = None,
    hardware_summary: Dict[str, object] | None = None,
    hardware_validation: Dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "communication-simulator.native-result.v1",
        "simulation_mode": simulation_mode,
        "created_utc": format_utc_timestamp(datetime.now(timezone.utc).timestamp()),
        "duration_s": duration_s,
        "bus_type": bus_type,
        "channels": channel_count,
        "nominal_bitrate": nominal_bitrate,
        "data_bitrate": data_bitrate,
        "artifacts": [str(item) for item in written],
        "warnings": warnings,
        "routing_rows": routing_rows,
        "restbus": restbus_summary,
        "filter_system": filter_summary or {"enabled": False},
        "trace_quality": trace_quality_summary(),
        "signal_suggestions": signal_suggestions or suggest_signal_gaps(routing_rows, bus_type),
        "hardware_profile": hardware_summary or {"enabled": False},
        "hardware_validation": hardware_validation or {
            "valid": True,
            "mode": "non_invasive_validation",
            "findings": [],
        },
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def run_simulation(request: Dict[str, Any]) -> Dict[str, Any]:
    """Run the native CAN/Ethernet generator from a standalone configuration."""
    args = argparse.Namespace(
        out="realistic_can_trace.blf",
        dbc="realistic_can_network.dbc",
        out_dir="generated_native_simulation",
        formats="blf,dbc,json,csv",
        duration=10.0,
        messages=None,
        seed=42,
        routing_table=None,
        channels=4,
        bus="fd",
        classic_can=False,
        nominal_bitrate=500_000,
        fd_bitrate=2_000_000,
        xl_data_bitrate=None,
        eth_bitrate=1_000_000_000,
        eth_bitrates=None,
        eth_messages=None,
        simulation_mode="restbus",
        interface_out=None,
        config=None,
        scenario={},
        filter_system=None,
        filter_summary=None,
        hardware=None,
        hardware_summary=None,
        hardware_validation=None,
    )
    apply_simulation_config_to_args(args, request)

    bus_type = "classic" if args.classic_can else args.bus
    if bus_type == "classic":
        data_bitrate = None
    elif bus_type == "fd":
        data_bitrate = args.fd_bitrate or 2_000_000
    else:
        data_bitrate = args.xl_data_bitrate or CAN_XL_DATA_BITRATES["e"]
    channel_count = max(1, min(16, int(args.channels)))

    routing_rows: List[Dict[str, object]] | None = None
    restbus_summary: Dict[str, object] | None = None
    if args.routing_table:
        routing_rows = load_routing_table(Path(args.routing_table), channel_count)
    elif args.simulation_mode == "restbus":
        participants = restbus_participants_from_request(request, channel_count)
        routing_rows = build_restbus_routing_rows(participants, channel_count, max_routes=args.messages)
        restbus_summary = restbus_interface_summary(participants, routing_rows)

    num_messages = int(args.messages) if args.messages is not None else (len(routing_rows) if routing_rows is not None else 100)
    selected_formats = parse_formats(args.formats)
    args.eth_bitrates = parse_ethernet_bitrates(args.eth_bitrates)
    written, warnings = generate_format_package(
        formats=selected_formats,
        args=args,
        bus_type=bus_type,
        nominal_bitrate=int(args.nominal_bitrate),
        data_bitrate=data_bitrate,
        channel_count=channel_count,
        routing_rows=routing_rows,
        num_messages=num_messages,
    )
    interface_path = args.interface_out or Path(args.out_dir).resolve() / "simulation_interface.json"
    write_simulation_interface(
        Path(interface_path).resolve(),
        simulation_mode=args.simulation_mode,
        written=written,
        warnings=warnings,
        duration_s=float(args.duration),
        bus_type=bus_type,
        channel_count=channel_count,
        nominal_bitrate=int(args.nominal_bitrate),
        data_bitrate=data_bitrate,
        routing_rows=routing_rows,
        restbus_summary=restbus_summary,
        filter_summary=getattr(args, "filter_summary", None),
        signal_suggestions=getattr(args, "signal_suggestions", None),
        hardware_summary=getattr(args, "hardware_summary", None),
        hardware_validation=getattr(args, "hardware_validation", None),
    )
    return json.loads(Path(interface_path).read_text(encoding="utf-8"))


# -----------------------------
# Netzwerkdefinition
# -----------------------------

def add_data_signals(msg: MessageDef, can_fd: bool, external_signals: List[Dict[str, Any]] | None = None) -> None:
    external_records = external_signal_records(external_signals)
    if external_records:
        for record in external_records:
            msg.signals.append(
                SignalDef(
                    name=record["name"],
                    start_bit=record["start_bit"],
                    length=record["length"],
                    factor=record["factor"],
                    offset=record["offset"],
                    minimum=record["minimum"],
                    maximum=record["maximum"],
                    unit=record["unit"],
                    kind=record["kind"],
                )
            )
        return

    # Layout: Byte 0 CRC, Byte 1 Counter/Mux/Status, ab Byte 2 Nutzsignale.
    msg.signals.append(SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"))
    msg.signals.append(SignalDef("AliveCounter", 8, 4, 1, 0, 0, 15, "", "counter"))
    msg.signals.append(SignalDef("MuxState", 12, 4, 1, 0, 0, 15, "", "mux"))

    bit = 16
    signal_count = 12 if can_fd else 6
    length = 12 if can_fd else 8
    receiver = msg.receivers[0] if msg.receivers else ""
    signal_specs = signal_specs_for_message(msg.sender, receiver, msg.name, signal_count, length)
    for spec in signal_specs:
        # 12-bit Signale sind typisch kompakt und erlauben viele Signale in CAN-FD.
        if bit + length > msg.dlc * 8:
            break
        msg.signals.append(
            SignalDef(
                name=spec.name,
                start_bit=bit,
                length=length,
                factor=spec.factor,
                offset=spec.offset,
                minimum=spec.minimum,
                maximum=spec.maximum,
                unit=spec.unit,
                kind=spec.kind,
            )
        )
        bit += length

    if can_fd:
        for idx in range(ROUTE_INFO_LENGTH):
            start_bit = (ROUTE_INFO_START_BYTE + idx) * 8
            if start_bit + 8 > msg.dlc * 8:
                break
            msg.signals.append(
                SignalDef(
                    name=f"RouteInfoChar_{idx:02d}",
                    start_bit=start_bit,
                    length=8,
                    factor=1,
                    offset=0,
                    minimum=0,
                    maximum=255,
                    unit="ascii",
                    kind="route_info",
                )
            )


def add_response_signals(msg: MessageDef) -> None:
    msg.signals.extend(
        [
            SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"),
            SignalDef("ResponseCounter", 8, 4, 1, 0, 0, 15, "", "counter"),
            SignalDef("AckState", 12, 4, 1, 0, 0, 15, "", "ack"),
            SignalDef("ReceivedFrameId", 16, 11, 1, 0, 0, 2047, "", "diag"),
            SignalDef("ReceivedCounter", 27, 4, 1, 0, 0, 15, "", "diag"),
            SignalDef("ChecksumOk", 31, 1, 1, 0, 0, 1, "", "diag"),
            SignalDef("PayloadLength", 32, 8, 1, 0, 0, 64, "byte", "diag"),
            SignalDef("ErrorCode", 40, 8, 1, 0, 0, 255, "", "diag"),
            SignalDef("ProcessingTimeUs", 48, 16, 1, 0, 0, 65535, "us", "diag"),
        ]
    )

    if msg.dlc > 8:
        msg.signals.extend(
            [
                SignalDef("ResponseSequence", 64, 16, 1, 0, 0, 65535, "", "diag"),
                SignalDef("ReceivedCrc", 80, 8, 1, 0, 0, 255, "", "diag"),
                SignalDef("CalculatedCrc", 88, 8, 1, 0, 0, 255, "", "diag"),
            ]
        )


def build_messages(
    num_messages: int = 100,
    bus_type: str = "fd",
    seed: int = 42,
    channel_count: int = 2,
    routing_rows: List[Dict[str, object]] | None = None,
) -> List[MessageDef]:
    random.seed(seed)
    can_fd_storage = bus_type in {"fd", "xl"}
    channel_count = max(1, min(16, channel_count))
    routing_rows = routing_rows or [
        normalized_routing_row(row, index, channel_count)
        for index, row in enumerate(DEFAULT_ROUTING_ROWS)
    ]

    messages: List[MessageDef] = []

    # CAN-FD: Signale + Counter + CRC passen in 64 Byte.
    # Classic CAN: 8 Byte, deshalb werden nur so viele Signale physisch codiert,
    # wie in 8 Byte passen. Metadaten bleiben als Kommentar/Name erhalten.
    # CAN XL wird hier logisch simuliert, aber als CAN-FD-kompatibler BLF gespeichert,
    # weil die installierte python-can/BLF-Version kein natives CAN-XL-Objekt anbietet.
    dlc = 64 if can_fd_storage else 8

    for i in range(num_messages):
        route = routing_rows[i % len(routing_rows)]
        sender = str(route["sender"])
        receiver = str(route["receiver"])
        cycle_ms = int(route["cycle_ms"])
        channel = int(route["channel"])
        gateway_to_channel = route["gateway_to_channel"]
        frame_id = int(route["frame_id"]) + (i // len(routing_rows)) * 0x20
        base_name = str(route["name"])

        msg = MessageDef(
            name=f"DATA_{i:03d}_{base_name}",
            frame_id=frame_id,
            sender=sender,
            receivers=[receiver],
            cycle_ms=cycle_ms,
            channel=channel,
            dlc=dlc,
            is_fd=can_fd_storage,
            bus_type=bus_type,
            gateway_to_channel=int(gateway_to_channel) if gateway_to_channel is not None else None,
            kind="data",
        )
        add_data_signals(msg, can_fd_storage, external_signals=route.get("signals"))
        messages.append(msg)

        response_dlc = 16 if can_fd_storage else 8
        response_msg = MessageDef(
            name=f"RESP_{i:03d}_{receiver}_TO_{sender}",
            frame_id=0x600 + i,
            sender=receiver,
            receivers=[sender],
            cycle_ms=cycle_ms,
            channel=channel,
            dlc=response_dlc,
            is_fd=can_fd_storage,
            bus_type=bus_type,
            kind="response",
            response_for=frame_id,
        )
        add_response_signals(response_msg)
        messages.append(response_msg)

    return messages


# -----------------------------
# Nutzdaten erzeugen
# -----------------------------

def encode_message_payload(
    msg: MessageDef,
    timestamp_s: float,
    alive_counter: int,
    inject_crc_error: bool = False,
    inject_counter_error: bool = False,
    inject_dlc_error: bool = False,
    filter_bank: Any | None = None,
) -> bytes:
    payload_len = msg.dlc
    if inject_dlc_error and payload_len > 8:
        payload_len = 32
    elif inject_dlc_error:
        payload_len = 7

    payload = bytearray(
        ((msg.frame_id + int(timestamp_s * 1000.0) + alive_counter * 31 + idx * 17) & 0xFF)
        for idx in range(payload_len)
    )

    counter_value = (alive_counter + (3 if inject_counter_error else 0)) & 0xF
    mux_value = int((timestamp_s * 10) % 16) & 0xF

    physical_index = 0
    for sig in msg.signals:
        if sig.start_bit + sig.length > payload_len * 8:
            continue
        if sig.kind == "crc":
            continue
        if sig.kind == "counter":
            value = counter_value
        elif sig.kind == "mux":
            value = mux_value
        elif sig.kind == "route_info":
            continue
        else:
            value = physical_raw_value(
                signal_name=sig.name,
                factor=sig.factor,
                offset=sig.offset,
                minimum=sig.minimum,
                maximum=sig.maximum,
                timestamp_s=timestamp_s,
                frame_id=msg.frame_id,
                signal_index=physical_index,
            )
            if filter_bank is not None:
                value = filter_bank.filter_value(
                    signal_name=sig.name,
                    sender=msg.sender,
                    receiver=msg.receivers[0] if msg.receivers else None,
                    role=None,
                    timestamp_s=timestamp_s,
                    measurement=value,
                    minimum=sig.minimum,
                    maximum=sig.maximum,
                )
            physical_index += 1
        set_unsigned_le(payload, sig.start_bit, sig.length, value)

    has_route_info = any(sig.kind == "route_info" for sig in msg.signals)
    if has_route_info and msg.is_fd and msg.receivers:
        route_bytes = route_label(msg.sender, msg.receivers[0]).encode("ascii", errors="replace")
        route_field = route_bytes[:ROUTE_INFO_LENGTH].ljust(ROUTE_INFO_LENGTH, b"\x00")
        start = ROUTE_INFO_START_BYTE
        end = min(start + ROUTE_INFO_LENGTH, len(payload))
        payload[start:end] = route_field[: end - start]

    has_payload_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in msg.signals)
    if has_payload_crc:
        crc_value = crc8_autosar(bytes(payload[1:]))
        if inject_crc_error:
            crc_value ^= 0x55
        set_unsigned_le(payload, 0, 8, crc_value)
    return bytes(payload)


def encode_response_payload(
    response_msg: MessageDef,
    request_msg: MessageDef,
    request_payload: bytes,
    response_counter: int,
    processing_time_us: int,
    response_sequence: int,
) -> bytes:
    payload = bytearray(
        ((response_msg.frame_id + response_counter * 19 + idx * 23) & 0xFF)
        for idx in range(response_msg.dlc)
    )

    has_request_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in request_msg.signals)
    has_request_counter = any("counter" in sig.kind.lower() or "counter" in sig.name.lower() for sig in request_msg.signals)
    received_crc = request_payload[0] if request_payload else 0
    calculated_crc = crc8_autosar(request_payload[1:]) if len(request_payload) >= 2 else 0
    checksum_ok = int((not has_request_crc) or (received_crc == calculated_crc and len(request_payload) >= 2))
    dlc_ok = int(len(request_payload) == request_msg.dlc)
    received_counter = get_unsigned_le(request_payload, 8, 4) if len(request_payload) > 1 else 0
    expected_counter = response_counter & 0xF
    counter_ok = int((not has_request_counter) or received_counter == expected_counter)

    error_code = 0
    if not checksum_ok:
        error_code |= 0x01
    if not dlc_ok:
        error_code |= 0x02
    if not counter_ok:
        error_code |= 0x04

    # 1 = Daten korrekt empfangen, 2 = CRC-Fehler, 3 = DLC-Fehler, 4 = Counter-Fehler.
    if error_code == 0:
        ack_state = 1
    elif error_code & 0x01:
        ack_state = 2
    elif error_code & 0x02:
        ack_state = 3
    else:
        ack_state = 4

    set_unsigned_le(payload, 8, 4, response_counter)
    set_unsigned_le(payload, 12, 4, ack_state)
    set_unsigned_le(payload, 16, 11, request_msg.frame_id)
    set_unsigned_le(payload, 27, 4, received_counter)
    set_unsigned_le(payload, 31, 1, checksum_ok)
    set_unsigned_le(payload, 32, 8, len(request_payload))
    set_unsigned_le(payload, 40, 8, error_code)
    set_unsigned_le(payload, 48, 16, processing_time_us)

    if response_msg.dlc > 8:
        set_unsigned_le(payload, 64, 16, response_sequence)
        set_unsigned_le(payload, 80, 8, received_crc)
        set_unsigned_le(payload, 88, 8, calculated_crc)

    set_unsigned_le(payload, 0, 8, crc8_autosar(bytes(payload[1:])))
    return bytes(payload)


# -----------------------------
# BLF Trace erzeugen
# -----------------------------

def iter_scheduled_events(messages: List[MessageDef], duration_s: float) -> Iterable[Tuple[float, MessageDef]]:
    for msg in messages:
        t = 0.0
        while t <= duration_s:
            # kleiner normaler Scheduler-Jitter im Mikro-/Millisekundenbereich
            jitter_s = random.uniform(-0.0004, 0.0008)
            yield max(0.0, t + jitter_s), msg
            t += msg.cycle_ms / 1000.0


def generate_blf(
    out_blf: Path,
    duration_s: float,
    bus_type: str,
    seed: int,
    num_messages: int = 100,
    nominal_bitrate: int | None = None,
    data_bitrate: int | None = None,
    channel_count: int = 2,
    routing_rows: List[Dict[str, object]] | None = None,
    start_utc: float | None = None,
    filter_bank: Any | None = None,
) -> List[MessageDef]:
    random.seed(seed)
    channel_count = max(1, min(16, channel_count))
    messages = build_messages(
        num_messages=num_messages,
        bus_type=bus_type,
        seed=seed,
        channel_count=channel_count,
        routing_rows=routing_rows,
    )
    trace_start_utc = datetime.now(timezone.utc).timestamp() if start_utc is None else start_utc

    data_messages = [m for m in messages if m.kind == "data"]
    response_by_request = {m.response_for: m for m in messages if m.kind == "response"}

    alive: Dict[int, int] = {m.frame_id: 0 for m in messages}
    events = sorted(iter_scheduled_events(data_messages, duration_s), key=lambda x: x[0])

    # Störszenarien: realistische, seltene Fehler
    dropout_probability = 0.0015
    crc_error_probability = 0.0010
    counter_error_probability = 0.0010
    dlc_error_probability = 0.0005
    timing_violation_probability = 0.0010

    bus_off_start = duration_s * 0.55
    bus_off_end = bus_off_start + 0.25
    bus_off_channel = 1 if channel_count > 1 else None

    recorded_messages = []
    can_fd_storage = bus_type in {"fd", "xl"}

    def append_control_frame(rel_time_s: float, channel: int, arbitration_id: int, sender: str, receiver: str, payload_text: str) -> None:
        payload = bytearray(64 if can_fd_storage else 8)
        encoded = payload_text.encode("ascii", errors="replace")[: len(payload) - 1]
        payload[1 : 1 + len(encoded)] = encoded
        payload[0] = crc8_autosar(bytes(payload[1:]))
        recorded_messages.append(
            CanMessage(
                timestamp=trace_start_utc + rel_time_s,
                arbitration_id=arbitration_id,
                is_extended_id=False,
                is_fd=can_fd_storage,
                bitrate_switch=can_fd_storage,
                error_state_indicator=False,
                dlc=len(payload),
                data=bytes(payload),
                channel=channel,
                is_rx=False,
            )
        )

    routed_messages = [msg for msg in data_messages if msg.gateway_to_channel is not None]
    for index, msg in enumerate(routed_messages[:8]):
        base = 0.002 + index * 0.006
        append_control_frame(base, msg.channel, 0x080 + index, msg.sender, "CENTRAL_GATEWAY", f"NM_WAKE {msg.sender}")
        append_control_frame(base + 0.0015, msg.channel, 0x0A0 + index, "CENTRAL_GATEWAY", msg.receivers[0], f"ROUTE_OPEN {msg.sender}->{msg.receivers[0]}")
        append_control_frame(base + 0.0030, msg.channel, 0x0C0 + index, msg.sender, msg.receivers[0], f"CONNECT {msg.sender}->{msg.receivers[0]}")
        append_control_frame(base + 0.0045, msg.channel, 0x0E0 + index, msg.receivers[0], msg.sender, f"ACK CONNECT {msg.receivers[0]}")

    for timestamp_s, msg in events:
        absolute_timestamp_s = trace_start_utc + timestamp_s

        # Bus-Off Pause auf einem Kanal
        if bus_off_channel is not None and msg.channel == bus_off_channel and bus_off_start <= timestamp_s <= bus_off_end:
            continue

        # Dropout / Lost frame
        if random.random() < dropout_probability:
            alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF
            continue

        if random.random() < timing_violation_probability:
            # zu frühe oder zu späte Botschaft
            timestamp_s += random.choice([-1, 1]) * random.uniform(0.003, 0.015)
            timestamp_s = max(0.0, timestamp_s)
            absolute_timestamp_s = trace_start_utc + timestamp_s

        inject_crc = random.random() < crc_error_probability
        inject_counter = random.random() < counter_error_probability
        inject_dlc = random.random() < dlc_error_probability

        data = encode_message_payload(
            msg,
            timestamp_s,
            alive[msg.frame_id],
            inject_crc_error=inject_crc,
            inject_counter_error=inject_counter,
            inject_dlc_error=inject_dlc,
            filter_bank=filter_bank,
        )

        can_msg = CanMessage(
            timestamp=absolute_timestamp_s,
            arbitration_id=msg.frame_id,
            is_extended_id=False,
            is_fd=msg.is_fd,
            bitrate_switch=msg.is_fd,
            error_state_indicator=False,
            dlc=len(data),
            data=data,
            channel=msg.channel,
            is_rx=False,
        )
        recorded_messages.append(can_msg)

        response_msg = response_by_request.get(msg.frame_id)
        if response_msg is not None:
            processing_time_us = random.randint(350, 1800)
            response_data = encode_response_payload(
                response_msg=response_msg,
                request_msg=msg,
                request_payload=data,
                response_counter=alive[msg.frame_id],
                processing_time_us=processing_time_us,
                response_sequence=alive[response_msg.frame_id],
            )
            response_can_msg = CanMessage(
                timestamp=absolute_timestamp_s + processing_time_us / 1_000_000.0,
                arbitration_id=response_msg.frame_id,
                is_extended_id=False,
                is_fd=response_msg.is_fd,
                bitrate_switch=response_msg.is_fd,
                error_state_indicator=False,
                dlc=len(response_data),
                data=response_data,
                channel=response_msg.channel,
                is_rx=True,
            )
            recorded_messages.append(response_can_msg)
            alive[response_msg.frame_id] = (alive[response_msg.frame_id] + 1) & 0xF

        # Gateway: jedes 10. Signal wird auf anderen Kanal gespiegelt,
        # mit neuer ID und realistischem Gateway-Delay.
        if msg.gateway_to_channel is not None:
            gw_data = bytearray(data)
            if any(sig.kind == "route_info" for sig in msg.signals) and len(gw_data) > 1:
                gw_data[1] ^= 0x80  # Gateway-Statusbit simuliert
            gw_msg = CanMessage(
                timestamp=absolute_timestamp_s + random.uniform(0.001, 0.004),
                arbitration_id=0x500 + (msg.frame_id & 0xFF),
                is_extended_id=False,
                is_fd=msg.is_fd,
                bitrate_switch=msg.is_fd,
                error_state_indicator=False,
                dlc=len(gw_data),
                data=bytes(gw_data),
                channel=msg.gateway_to_channel,
                is_rx=False,
            )
            recorded_messages.append(gw_msg)

        alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF

    with BLFWriter(str(out_blf)) as writer:
        for can_msg in sorted(recorded_messages, key=lambda item: item.timestamp):
            writer.on_message_received(can_msg)

    return messages


# -----------------------------
# DBC schreiben
# -----------------------------

def write_dbc(
    path: Path,
    messages: List[MessageDef],
    nominal_bitrate: int | None = None,
    data_bitrate: int | None = None,
) -> None:
    nodes = sorted({m.sender for m in messages} | {r for m in messages for r in m.receivers})

    lines: List[str] = []
    lines.append('VERSION "Realistic CAN Trace Generator"')
    lines.append('')
    lines.append('NS_ :')
    lines.append('\tNS_DESC_')
    lines.append('\tCM_')
    lines.append('\tBA_DEF_')
    lines.append('\tBA_')
    lines.append('\tVAL_')
    lines.append('')
    lines.append('BS_:')
    lines.append('')
    lines.append('BU_: ' + ' '.join(nodes))
    lines.append('')

    for msg in messages:
        lines.append(f'BO_ {msg.frame_id} {msg.name}: {msg.dlc} {msg.sender}')
        for sig in msg.signals:
            receivers = ','.join(msg.receivers)
            endian = '1'  # Intel/little endian
            signed = '+'
            lines.append(
                f' SG_ {sig.name} : {sig.start_bit}|{sig.length}@{endian}{signed} '
                f'({sig.factor},{sig.offset}) [{sig.minimum}|{sig.maximum}] "{sig.unit}" {receivers}'
            )
        gw = f' Gateway to CAN{msg.gateway_to_channel}' if msg.gateway_to_channel is not None else ''
        if msg.bus_type == "xl":
            bus_label = " CAN-XL"
        elif msg.bus_type == "fd":
            bus_label = " CAN-FD"
        else:
            bus_label = " Classic-CAN"
        nominal_info = f' NominalBitrate={nominal_bitrate // 1000}kbit/s;' if nominal_bitrate else ''
        data_info = f' DataBitrate={data_bitrate // 1000}kbit/s;' if msg.bus_type in {"fd", "xl"} and data_bitrate else ''
        xl_info = ' NativeCanXl=false; StoredAs=CAN-FD-compatible-BLF;' if msg.bus_type == "xl" else ''
        if msg.kind == "response":
            relation = f' ResponseFor=0x{msg.response_for:X}; ACK/NACK with CRC, DLC and counter check;'
        else:
            route = route_label(msg.sender, msg.receivers[0]) if msg.receivers else msg.sender
            if any(sig.kind == "route_info" for sig in msg.signals):
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"PayloadRouteInfo='{route}' in bytes {ROUTE_INFO_START_BYTE}-"
                    f'{ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH - 1};'
                )
            elif msg.is_fd:
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"ExternalSignalLayout=preserved; PayloadRouteInfo not injected;"
                )
            else:
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"PayloadRouteInfo='{route}' only in DBC comment because Classic CAN payload is 8 bytes;"
                )
        lines.append(
            f'CM_ BO_ {msg.frame_id} "Cycle={msg.cycle_ms}ms; Channel=CAN{msg.channel};'
            f'{bus_label};{nominal_info}{data_info}{xl_info} {relation}{gw}";'
        )
        lines.append('')

    path.write_text('\n'.join(lines), encoding='utf-8')


# -----------------------------
# ASC optional als Debug
# -----------------------------

def validate_blf(path: Path) -> Tuple[int, float, float]:
    count = 0
    first = math.inf
    last = 0.0
    with BLFReader(str(path)) as reader:
        for msg in reader:
            count += 1
            first = min(first, msg.timestamp)
            last = max(last, msg.timestamp)
    return count, first if first != math.inf else 0.0, last

def format_bitrate(value: int) -> str:
    if value >= 1_000_000:
        mbps = value / 1_000_000
        return f"{mbps:g} Mbit/s"
    return f"{value // 1000:g} kbit/s"


def format_utc_timestamp(timestamp_s: float) -> str:
    return datetime.fromtimestamp(timestamp_s, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def choose_bitrate(title: str, options: Dict[str, int], default_value: int) -> int:
    numbered_options = list(options.values())
    if default_value not in numbered_options:
        raise ValueError(f"Default-Bitrate {default_value} ist keine erlaubte Option.")

    print(title)
    for index, value in enumerate(numbered_options, start=1):
        default_suffix = " (Default)" if value == default_value else ""
        print(f"{index}. {format_bitrate(value)}{default_suffix}")

    allowed = "/".join(str(index) for index in range(1, len(numbered_options) + 1))
    selected = input(f"Geben Sie Ihre Auswahl ein [{allowed}], Enter = {format_bitrate(default_value)}: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not 1 <= int(selected) <= len(numbered_options):
        print(f"Ungültige Eingabe. Bitte geben Sie eine Zahl von 1 bis {len(numbered_options)} ein oder drücken Sie Enter.")
        selected = input(f"Geben Sie Ihre Auswahl ein [{allowed}], Enter = {format_bitrate(default_value)}: ").strip()
        if selected == "":
            return default_value
    return numbered_options[int(selected) - 1]


def choose_channel_count(default_value: int = 2) -> int:
    selected = input(f"Wie viele CAN-Kanäle sollen im Trace sein? [1-16, Enter = {default_value}, erzeugt CAN0 bis CAN15]: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not 1 <= int(selected) <= 16:
        print("Ungültige Eingabe. Bitte geben Sie eine Zahl von 1 bis 16 ein oder drücken Sie Enter.")
        selected = input(f"Wie viele CAN-Kanäle sollen im Trace sein? [1-16, Enter = {default_value}]: ").strip()
        if selected == "":
            return default_value
    return int(selected)


def choose_positive_int(title: str, default_value: int, minimum: int = 1, maximum: int = 500) -> int:
    selected = input(f"{title} [{minimum}-{maximum}, Enter = {default_value}]: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not minimum <= int(selected) <= maximum:
        print(f"Ungültige Eingabe. Bitte geben Sie eine Zahl von {minimum} bis {maximum} ein oder drücken Sie Enter.")
        selected = input(f"{title} [{minimum}-{maximum}, Enter = {default_value}]: ").strip()
        if selected == "":
            return default_value
    return int(selected)


def choose_mode(title: str, modes: Dict[str, str], default_value: str | None = None) -> str:
    if title:
        print(title)
    for key, label in modes.items():
        default_suffix = " (Default)" if key == default_value else ""
        print(f"{key}. {label}{default_suffix}")

    prompt_default = f", Enter = {default_value}" if default_value is not None else ""
    selected = input(f"Geben Sie Ihre Auswahl ein [{'/'.join(modes)}{prompt_default}]: ").strip()
    if selected == "" and default_value is not None:
        return default_value
    while selected not in modes:
        print(f"Ungültige Eingabe. Bitte geben Sie {', '.join(modes)} ein.")
        selected = input(f"Geben Sie Ihre Auswahl ein [{'/'.join(modes)}{prompt_default}]: ").strip()
        if selected == "" and default_value is not None:
            return default_value
    return selected


def choose_multi_mode(title: str, modes: Dict[str, str], default_values: List[str]) -> List[str]:
    if title:
        print(title)
    for key, label in modes.items():
        default_suffix = " (Default)" if key in default_values else ""
        print(f"{key}. {label}{default_suffix}")

    allowed = "/".join(modes)
    default_text = ",".join(default_values)
    prompt = f"Geben Sie eine oder mehrere Auswahlen ein [{allowed}], z.B. 1,2, Enter = {default_text}: "
    selected = input(prompt).strip()
    if selected == "":
        return default_values

    while True:
        if selected.lower() in {"all", "alle", "a"}:
            return list(modes)
        parts = [part for part in re.split(r"[\s,;/]+", selected) if part]
        if parts and all(part in modes for part in parts):
            result: List[str] = []
            for part in parts:
                if part not in result:
                    result.append(part)
            return result
        print(f"Ungültige Eingabe. Bitte geben Sie eine oder mehrere Zahlen aus {', '.join(modes)} ein.")
        selected = input(prompt).strip()
        if selected == "":
            return default_values


def choose_can_profile(title: str, default_value: str = "fd") -> Tuple[str, int, int | None]:
    mode_choice = choose_mode(
        title,
        {
            "1": "Classic CAN",
            "2": "CAN-FD",
            "3": "CAN-XL Profil (BLF wird CAN-FD-kompatibel gespeichert)",
        },
        default_value={"classic": "1", "fd": "2", "xl": "3"}[default_value],
    )
    bus_type = {"1": "classic", "2": "fd", "3": "xl"}[mode_choice]
    nominal_bitrate = choose_bitrate("Nominale/arbitration Datenrate:", COMMON_NOMINAL_BITRATES, 500_000)
    data_bitrate: int | None = None
    if bus_type == "fd":
        data_bitrate = choose_bitrate("CAN-FD Datenphase:", CAN_FD_DATA_BITRATES, 2_000_000)
    elif bus_type == "xl":
        data_bitrate = choose_bitrate("CAN-XL Datenphase:", CAN_XL_DATA_BITRATES, 10_000_000)
    return bus_type, nominal_bitrate, data_bitrate


def choose_ethernet_formats() -> List[str]:
    selected = choose_multi_mode(
        "Ethernet-Ausgabearten:",
        {
            "1": "PCAP",
            "2": "PCAPNG",
        },
        default_values=["1", "2"],
    )
    return [{"1": "pcap", "2": "pcapng"}[item] for item in selected]


def choose_ethernet_bitrates() -> List[int]:
    bitrates = list(ETHERNET_BITRATES.values())
    modes = {str(index): format_bitrate(value) for index, value in enumerate(bitrates, start=1)}
    selected = choose_multi_mode("Ethernet-Geschwindigkeiten:", modes, default_values=["3"])
    return [bitrates[int(item) - 1] for item in selected]


def choice() -> Dict[str, object]:
    print("Wählen Sie den Modus:")
    mode_choice = choose_mode(
        "",
        {
            "1": "Realistischer CAN Trace (Classic CAN)",
            "2": "Realistischer CAN-FD Trace",
            "3": "Logisches CAN-XL Profil",
            "4": "Ethernet Trace (PCAP/PCAPNG)",
            "5": "Mixed Trace (CAN + Ethernet)",
        },
        default_value="2",
    )

    nominal_bitrate = 500_000
    data_bitrate: int | None = None
    channel_count = 0
    bus_type = "fd"
    formats = "blf,dbc"
    out_dir: str | None = None
    eth_bitrates: List[int] = []
    eth_messages: int | None = None

    if mode_choice in {"1", "2", "3"}:
        bus_type = {"1": "classic", "2": "fd", "3": "xl"}[mode_choice]
        nominal_bitrate = choose_bitrate("Nominale/arbitration Datenrate:", COMMON_NOMINAL_BITRATES, 500_000)
        if bus_type == "fd":
            data_bitrate = choose_bitrate("CAN-FD Datenphase:", CAN_FD_DATA_BITRATES, 2_000_000)
        elif bus_type == "xl":
            data_bitrate = choose_bitrate("CAN-XL Datenphase:", CAN_XL_DATA_BITRATES, 10_000_000)
        channel_count = choose_channel_count(default_value=2)
    elif mode_choice == "4":
        formats = ",".join(choose_ethernet_formats())
        out_dir = "generated_ethernet_trace"
    else:
        bus_type, nominal_bitrate, data_bitrate = choose_can_profile("CAN-Anteil im Mixed-Modus:", default_value="fd")
        channel_count = choose_channel_count(default_value=2)
        formats = ",".join(["can-all", *choose_ethernet_formats()])
        out_dir = "generated_mixed_trace"
        print("Mixed-Modus: erzeugt CAN-Dateien, Ethernet-Dateien und eine gemeinsame mixed_trace.json.")

    if mode_choice in {"4", "5"}:
        eth_bitrates = choose_ethernet_bitrates()
        eth_messages = choose_positive_int("Wie viele Ethernet-Kommunikationsströme sollen erzeugt werden?", default_value=4)

    return {
        "mode_choice": mode_choice,
        "bus_type": bus_type,
        "nominal_bitrate": nominal_bitrate,
        "data_bitrate": data_bitrate,
        "channel_count": channel_count,
        "eth_bitrate": eth_bitrates[0] if eth_bitrates else None,
        "eth_bitrates": eth_bitrates,
        "eth_messages": eth_messages,
        "formats": formats,
        "out_dir": out_dir,
    }


FORMAT_GROUPS = {
    "can-all": {"blf", "dbc", "asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex"},
    "eth-all": {"pcap", "pcapng"},
    "optional-all": {"mdf", "mf4"},
}
FORMAT_GROUPS["all"] = FORMAT_GROUPS["can-all"] | FORMAT_GROUPS["eth-all"]
SUPPORTED_FORMATS = FORMAT_GROUPS["all"] | FORMAT_GROUPS["optional-all"]
DATABASE_FORMATS = {"dbc", "arxml", "fibex"}


def parse_formats(value: str) -> List[str]:
    requested = [part.strip().lower() for part in value.split(",") if part.strip()]
    formats: List[str] = []
    for item in requested:
        expanded = FORMAT_GROUPS.get(item, {item})
        for fmt in sorted(expanded):
            if fmt not in SUPPORTED_FORMATS:
                allowed = ", ".join(sorted(SUPPORTED_FORMATS | set(FORMAT_GROUPS)))
                raise ValueError(f"Unbekanntes Format '{item}'. Erlaubt: {allowed}")
            if fmt not in formats:
                formats.append(fmt)
    return formats


def add_format_generators_to_path() -> None:
    generator_dir = Path(__file__).resolve().parent / "format_generators"
    generator_dir_text = str(generator_dir)
    if generator_dir_text not in sys.path:
        sys.path.insert(0, generator_dir_text)


def package_output_path(out_dir: Path, fmt: str) -> Path:
    names = {
        "blf": "trace.blf",
        "dbc": "network.dbc",
        "asc": "trace.asc",
        "trc": "trace.trc",
        "csv": "trace.csv",
        "json": "trace.json",
        "log": "trace.log",
        "txt": "trace.txt",
        "xml": "trace.xml",
        "yaml": "trace.yaml",
        "yml": "trace.yml",
        "arxml": "system.arxml",
        "fibex": "system.fibex.xml",
        "pcap": "someip.pcap",
        "pcapng": "someip.pcapng",
        "mdf": "summary.mdf",
        "mf4": "summary.mf4",
    }
    subdir = "datenbasen" if fmt in DATABASE_FORMATS else "traces"
    path = out_dir / subdir / names[fmt]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def bitrate_filename_slug(value: int) -> str:
    if value >= 1_000_000:
        return f"{value // 1_000_000}mbit"
    return f"{value // 1000}kbit"


def ethernet_output_path(out_dir: Path, fmt: str, bitrate: int, include_bitrate: bool) -> Path:
    if not include_bitrate:
        return package_output_path(out_dir, fmt)
    stem = "someip"
    path = out_dir / "traces" / f"{stem}_{bitrate_filename_slug(bitrate)}.{fmt}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parse_ethernet_bitrates(value: object) -> List[int]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
    else:
        parts = [part.strip() for part in str(value).split(",") if part.strip()]
    bitrates: List[int] = []
    allowed = set(ETHERNET_BITRATES.values())
    for part in parts:
        bitrate = int(part, 0)
        if bitrate not in allowed:
            allowed_text = ", ".join(str(item) for item in sorted(allowed))
            raise ValueError(f"Unbekannte Ethernet-Geschwindigkeit '{part}'. Erlaubt: {allowed_text}")
        if bitrate not in bitrates:
            bitrates.append(bitrate)
    return bitrates


def write_manifest(path: Path, metadata: Dict[str, object]) -> None:
    path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def archive_trace_package_to_library(out_dir: Path, package_type: str) -> Path | None:
    """Return the generated package path without creating runtime copies."""
    source = Path(out_dir).resolve()
    if not source.exists() or not source.is_dir():
        return None
    return source


def archive_generated_files_to_library(paths: Iterable[Path], category: str) -> Path | None:
    """Runtime artifacts are never copied into the source/profile library."""
    return None


def package_type_from_formats(formats: List[str]) -> str:
    has_can_output = any(fmt in FORMAT_GROUPS["can-all"] or fmt in FORMAT_GROUPS["optional-all"] for fmt in formats)
    has_eth_output = any(fmt in FORMAT_GROUPS["eth-all"] for fmt in formats)
    return "mixed" if has_can_output and has_eth_output else "ethernet" if has_eth_output else "can"


def route_generated_out_dir_to_library(args: argparse.Namespace, formats: List[str]) -> None:
    out_dir_value = args.out_dir or "generated_trace_package"
    out_dir = Path(str(out_dir_value))
    if out_dir.is_absolute():
        return
    try:
        out_dir.relative_to(TRACE_ROOT)
        return
    except ValueError:
        pass
    if not out_dir.name.startswith("generated_"):
        return
    args.out_dir = str(TRACE_ROOT / out_dir.name)


def write_mixed_trace(
    path: Path,
    can_frames: List[object],
    eth_frames: List[object],
    metadata: Dict[str, object],
    trace_start_utc: float,
) -> None:
    entries: List[Dict[str, object]] = []
    for frame in can_frames:
        entries.append(
            {
                "timestamp": frame.timestamp,
                "timestamp_utc": format_utc_timestamp(frame.timestamp),
                "trace_time_s": frame.timestamp - trace_start_utc,
                "rel_time": frame.rel_time,
                "protocol": "CAN",
                "channel": f"CAN{frame.channel}",
                "id": f"0x{frame.arbitration_id:X}",
                "name": frame.name,
                "sender": frame.sender,
                "receiver": frame.receiver,
                "direction": frame.direction,
                "bus_type": frame.bus_type,
                "dlc": frame.dlc,
                "payload_hex": frame.data.hex(" ").upper(),
                "message_kind": frame.message_kind,
            }
        )
    for frame in eth_frames:
        entries.append(
            {
                "timestamp": frame.timestamp,
                "timestamp_utc": format_utc_timestamp(frame.timestamp),
                "trace_time_s": frame.timestamp - trace_start_utc,
                "rel_time": frame.rel_time,
                "protocol": "ETH",
                "src_node": frame.src_node,
                "dst_node": frame.dst_node,
                "src_mac": frame.src_mac,
                "dst_mac": frame.dst_mac,
                "src_ip": frame.src_ip,
                "dst_ip": frame.dst_ip,
                "src_port": frame.src_port,
                "dst_port": frame.dst_port,
                "service_id": f"0x{frame.service_id:04X}",
                "method_id": f"0x{frame.method_id:04X}",
                "message_type": f"0x{frame.message_type:02X}",
                "payload_hex": frame.payload.hex(" ").upper(),
            }
        )

    entries.sort(key=lambda item: (float(item["timestamp"]), str(item["protocol"])))
    path.write_text(
        json.dumps(
            {
                "trace_type": "mixed",
                "metadata": metadata,
                "frames": entries,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def generate_format_package(
    formats: List[str],
    args: argparse.Namespace,
    bus_type: str,
    nominal_bitrate: int,
    data_bitrate: int | None,
    channel_count: int,
    routing_rows: List[Dict[str, object]] | None,
    num_messages: int,
    progress: ProgressBar | None = None,
) -> Tuple[List[Path], List[str]]:
    if progress:
        progress.update(5, "Bereite Dateipaket vor")
    add_format_generators_to_path()
    from can_format_writers import (
        write_arxml as suite_write_arxml,
        write_asc,
        write_csv_trace,
        write_dbc as suite_write_dbc,
        write_fibex as suite_write_fibex,
        write_json_trace,
        write_log,
        write_trc,
        write_txt,
        write_xml_trace,
        write_yaml_trace,
    )
    from common_trace import build_can_trace, build_ethernet_trace
    from eth_format_writers import write_pcap, write_pcapng

    out_dir = Path(args.out_dir or "generated_trace_package").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_start_utc = datetime.now(timezone.utc).timestamp()

    written: List[Path] = []
    warnings: List[str] = []
    can_formats = [fmt for fmt in formats if fmt in FORMAT_GROUPS["can-all"] or fmt in FORMAT_GROUPS["optional-all"]]
    eth_formats = [fmt for fmt in formats if fmt in FORMAT_GROUPS["eth-all"]]
    mixed_enabled = bool(can_formats and eth_formats)
    eth_bitrates = parse_ethernet_bitrates(getattr(args, "eth_bitrates", None))
    if not eth_bitrates and eth_formats:
        eth_bitrates = [int(getattr(args, "eth_bitrate", 1_000_000_000))]
    eth_message_count = int(getattr(args, "eth_messages", None) or num_messages)
    suite_messages = None
    suite_frames = None
    eth_frames = None
    scenario = getattr(args, "scenario", {}) if isinstance(getattr(args, "scenario", {}), dict) else {}
    filter_banks = []

    def new_filter_bank():
        bank = create_filter_bank(getattr(args, "filter_system", None), scenario)
        if bank is not None:
            filter_banks.append(bank)
        return bank

    root_messages: List[MessageDef] | None = None
    if "blf" in formats:
        if progress:
            progress.update(15, "Erzeuge BLF Trace")
        blf_filter_bank = new_filter_bank()
        blf_path = package_output_path(out_dir, "blf")
        root_messages = generate_blf(
            out_blf=blf_path,
            duration_s=args.duration,
            bus_type=bus_type,
            seed=args.seed,
            num_messages=num_messages,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            channel_count=channel_count,
            routing_rows=routing_rows,
            start_utc=trace_start_utc,
            filter_bank=blf_filter_bank,
        )
        written.append(blf_path)

    if "dbc" in formats:
        if progress:
            progress.update(28, "Schreibe DBC Datenbank")
        dbc_path = package_output_path(out_dir, "dbc")
        if root_messages is None:
            root_messages = build_messages(
                num_messages=num_messages,
                bus_type=bus_type,
                seed=args.seed,
                channel_count=channel_count,
                routing_rows=routing_rows,
            )
        write_dbc(dbc_path, root_messages, nominal_bitrate=nominal_bitrate, data_bitrate=data_bitrate)
        written.append(dbc_path)

    if any(fmt in formats for fmt in {"asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex"}):
        if progress:
            progress.update(42, "Erzeuge CAN Zusatzformate")
        suite_filter_bank = new_filter_bank()
        suite_messages, suite_frames = build_can_trace(
            duration=args.duration,
            messages=num_messages,
            channels=channel_count,
            bus_type=bus_type,
            seed=args.seed,
            start_utc=trace_start_utc,
            routing_rows=routing_rows,
            filter_bank=suite_filter_bank,
        )
        writer_map = {
            "asc": lambda p: write_asc(p, suite_frames, trace_start_utc=trace_start_utc),
            "trc": lambda p: write_trc(p, suite_frames, trace_start_utc=trace_start_utc),
            "csv": lambda p: write_csv_trace(p, suite_frames),
            "json": lambda p: write_json_trace(p, suite_frames),
            "log": lambda p: write_log(p, suite_frames),
            "txt": lambda p: write_txt(p, suite_frames),
            "xml": lambda p: write_xml_trace(p, suite_frames),
            "yaml": lambda p: write_yaml_trace(p, suite_frames),
            "yml": lambda p: write_yaml_trace(p, suite_frames),
            "arxml": lambda p: suite_write_arxml(p, suite_messages),
            "fibex": lambda p: suite_write_fibex(p, suite_messages),
        }
        for fmt, writer in writer_map.items():
            if fmt in formats:
                if progress:
                    progress.update(45 + min(15, len(written)), f"Schreibe {fmt.upper()}")
                path = package_output_path(out_dir, fmt)
                writer(path)
                written.append(path)

    if eth_formats:
        if progress:
            progress.update(66, "Erzeuge Ethernet Frames")
        eth_frames = build_ethernet_trace(duration=args.duration, messages=eth_message_count, seed=args.seed, start_utc=trace_start_utc)
        include_bitrate_in_name = len(eth_bitrates) > 1
        for eth_bitrate in eth_bitrates:
            if "pcap" in formats:
                if progress:
                    progress.update(72, "Schreibe PCAP")
                path = ethernet_output_path(out_dir, "pcap", eth_bitrate, include_bitrate_in_name)
                write_pcap(path, eth_frames)
                written.append(path)
            if "pcapng" in formats:
                if progress:
                    progress.update(76, "Schreibe PCAPNG")
                path = ethernet_output_path(out_dir, "pcapng", eth_bitrate, include_bitrate_in_name)
                write_pcapng(path, eth_frames)
                written.append(path)

    for fmt, version in (("mdf", "3.30"), ("mf4", "4.10")):
        if fmt not in formats:
            continue
        path = package_output_path(out_dir, fmt)
        try:
            if progress:
                progress.update(82, f"Schreibe {fmt.upper()}")
            from mdf_writer import write_mdf

            write_mdf(path, version, args.duration, num_messages, channel_count, bus_type, args.seed, routing_rows=routing_rows)
            written.append(path)
        except SystemExit as exc:
            warnings.append(f"{fmt.upper()} nicht erzeugt: {exc}")

    if mixed_enabled:
        if progress:
            progress.update(88, "Schreibe Mixed Trace")
        if suite_frames is None:
            suite_filter_bank = new_filter_bank()
            suite_messages, suite_frames = build_can_trace(
                duration=args.duration,
                messages=num_messages,
                channels=channel_count,
                bus_type=bus_type,
                seed=args.seed,
                start_utc=trace_start_utc,
                routing_rows=routing_rows,
                filter_bank=suite_filter_bank,
            )
        if eth_frames is None:
            eth_frames = build_ethernet_trace(duration=args.duration, messages=eth_message_count, seed=args.seed, start_utc=trace_start_utc)
        mixed_path = out_dir / "traces" / "mixed_trace.json"
        mixed_path.parent.mkdir(parents=True, exist_ok=True)
        write_mixed_trace(
            mixed_path,
            suite_frames,
            eth_frames,
            {
                "duration_s": args.duration,
                "trace_start_utc": format_utc_timestamp(trace_start_utc),
                "trace_start_unix": trace_start_utc,
                "messages": num_messages,
                "ethernet_messages": eth_message_count,
                "can_frames": len(suite_frames),
                "ethernet_frames": len(eth_frames),
                "bus_type": bus_type,
                "nominal_bitrate": nominal_bitrate,
                "data_bitrate": data_bitrate,
                "ethernet_bitrates": eth_bitrates,
            },
            trace_start_utc=trace_start_utc,
        )
        written.append(mixed_path)

    if progress:
        progress.update(94, "Schreibe Manifest")
    can_frame_count = len(suite_frames) if suite_frames is not None else None
    ethernet_frame_count = len(eth_frames) if eth_frames is not None else None
    filter_summary = summarize_filter_banks(filter_banks, getattr(args, "filter_system", None), scenario)
    args.filter_summary = filter_summary
    signal_suggestions = suggest_signal_gaps(routing_rows, bus_type)
    args.signal_suggestions = signal_suggestions
    write_manifest(
        out_dir / "generation_manifest.json",
        {
            "package_type": "mixed" if mixed_enabled else "ethernet" if eth_formats else "can",
            "folders": {
                "traces": "traces",
                "databases": "datenbasen",
            },
            "formats": formats,
            "written": [str(path) for path in written],
            "warnings": warnings,
            "duration_s": args.duration,
            "trace_start_utc": format_utc_timestamp(trace_start_utc),
            "trace_start_unix": trace_start_utc,
            "messages": num_messages,
            "ethernet_messages": eth_message_count if eth_formats else None,
            "can_frames": can_frame_count,
            "ethernet_frames": ethernet_frame_count,
            "can_enabled": bool(can_formats),
            "ethernet_enabled": bool(eth_formats),
            "mixed_enabled": mixed_enabled,
            "channels": channel_count if can_formats else 0,
            "bus_type": bus_type if can_formats else None,
            "nominal_bitrate": nominal_bitrate if can_formats else None,
            "data_bitrate": data_bitrate if can_formats else None,
            "ethernet_bitrate": eth_bitrates[0] if eth_formats and eth_bitrates else None,
            "ethernet_bitrates": eth_bitrates if eth_formats else None,
            "routing_table": str(args.routing_table.resolve()) if args.routing_table else None,
            "filter_system": filter_summary,
            "trace_quality": trace_quality_summary(),
            "signal_suggestions": signal_suggestions,
            "hardware_profile": getattr(args, "hardware_summary", None) or {"enabled": False},
            "hardware_validation": getattr(args, "hardware_validation", None) or {
                "valid": True,
                "mode": "non_invasive_validation",
                "findings": [],
            },
        },
    )
    written.append(out_dir / "generation_manifest.json")
    return written, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Technologieoffener Communication Simulator mit optionalen nativen CAN/Ethernet-Writern"
    )
    parser.add_argument("--out", default="realistic_can_trace.blf", help="Ausgabe-BLF")
    parser.add_argument("--dbc", default="realistic_can_network.dbc", help="Ausgabe-DBC")
    parser.add_argument("--out-dir", default=None, help="Zielordner für Multi-Format-Ausgabe")
    parser.add_argument(
        "--formats",
        default="blf,dbc",
        help="Kommagetrennt: universal-jsonl,universal-csv sowie native Formate wie blf,dbc,pcapng",
    )
    parser.add_argument("--duration", type=float, default=60.0, help="Trace-Laufzeit in Sekunden")
    parser.add_argument("--messages", type=int, default=None, help="Anzahl Datenbotschaften; ohne Wert nimmt --routing-table die CSV-Zeilenzahl")
    parser.add_argument("--seed", type=int, default=42, help="Zufalls-Seed")
    parser.add_argument("--routing-table", type=Path, default=None, help="CSV-Routingtabelle mit sender,receiver,cycle_ms,channel,gateway_to_channel,frame_id,name")
    parser.add_argument("--write-routing-template", type=Path, default=None, help="Schreibt eine Beispiel-Routing-CSV und beendet das Programm")
    parser.add_argument("--config", type=Path, default=None, help="Standalone JSON-Simulationskonfiguration")
    parser.add_argument("--write-config-template", type=Path, default=None, help="Schreibt eine Standalone-Konfigurationsvorlage und beendet das Programm")
    parser.add_argument("--interface-out", type=Path, default=None, help="Schreibt eine JSON-Ergebnisdatei")
    parser.add_argument(
        "--simulation-mode",
        choices=["existing", "restbus"],
        default="existing",
        help="existing nutzt Routing-Tabelle/Default-Logik; restbus erzeugt Routen aus Teilnehmern",
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=range(1, 17),
        default=2,
        metavar="1-16",
        help="Anzahl CAN-Kanäle im Trace; 16 erzeugt CAN0 bis CAN15",
    )
    parser.add_argument("--bus", choices=["classic", "fd", "xl"], default="fd", help="Busprofil: classic, fd oder xl")
    parser.add_argument("--classic-can", action="store_true", help="Classic CAN statt CAN-FD erzeugen")
    parser.add_argument(
        "--nominal-bitrate",
        type=int,
        choices=sorted(COMMON_NOMINAL_BITRATES.values()),
        default=500_000,
        help="Nominale/arbitration Datenrate in bit/s",
    )
    parser.add_argument(
        "--fd-bitrate",
        type=int,
        choices=sorted(CAN_FD_DATA_BITRATES.values()),
        default=None,
        help="CAN-FD Datenphase in bit/s",
    )
    parser.add_argument(
        "--xl-data-bitrate",
        type=int,
        choices=sorted(CAN_XL_DATA_BITRATES.values()),
        default=None,
        help="CAN-XL Datenphase in bit/s",
    )
    parser.add_argument(
        "--eth-bitrate",
        type=int,
        choices=sorted(ETHERNET_BITRATES.values()),
        default=1_000_000_000,
        help="Ethernet Datenrate in bit/s für Manifest/Metadaten",
    )
    parser.add_argument(
        "--eth-bitrates",
        default=None,
        help="Kommagetrennte Ethernet-Datenraten in bit/s, z.B. 100000000,1000000000",
    )
    parser.add_argument(
        "--eth-messages",
        type=int,
        default=None,
        help="Anzahl Ethernet-Kommunikationsströme; ohne Wert wird --messages verwendet",
    )
    parser.add_argument(
        "--technology",
        choices=sorted(DEFAULT_TECHNOLOGY_REGISTRY.builtin),
        default=None,
        help="Bus- oder Protokolltechnologie für die universelle Standalone-Simulation",
    )
    parser.add_argument(
        "--list-technologies",
        action="store_true",
        help="Zeigt alle registrierten Technologien nach Branche gruppiert an",
    )
    parser.add_argument("--industry", default=None, help="Optionale Branchenzuordnung")
    parser.add_argument(
        "--bitrate",
        type=int,
        default=None,
        help="Technologie-Bitrate in bit/s; Standardwert kommt aus der Registry",
    )
    parser.add_argument("--nodes", type=int, default=2, help="Anzahl Hardware-Knoten, mindestens 2")
    parser.add_argument(
        "--cycle-ms",
        type=float,
        default=100.0,
        help="Kommunikationszyklus der universellen Route in Millisekunden",
    )
    parser.add_argument(
        "--payload-bytes",
        type=int,
        default=None,
        help="Payload-Größe; wird gegen die Technologiegrenze geprüft",
    )
    parser.add_argument("--max-events", type=int, default=None, help="Maximale Anzahl neutraler Trace-Events")
    parser.add_argument(
        "--dropout-probability",
        type=float,
        default=0.0,
        help="Dropout-Wahrscheinlichkeit von 0.0 bis 1.0",
    )
    parser.add_argument(
        "--corruption-probability",
        type=float,
        default=0.0,
        help="Korruptionswahrscheinlichkeit von 0.0 bis 1.0",
    )
    parser.add_argument("--network-id", default=None, help="Optionale ID des simulierten Netzwerks")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validiert Hardware und Topologie ohne Trace-Erzeugung",
    )
    parser.add_argument(
        "--native-cli",
        action="store_true",
        help="Erzwingt den bisherigen nativen CAN/Ethernet-CLI-Pfad",
    )
    args = parser.parse_args()

    if args.list_technologies:
        print(f"Registrierte Technologien: {len(DEFAULT_TECHNOLOGY_REGISTRY.builtin)}")
        for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
            print(f"\n{generator.domain}:")
            for technology_id, profile in generator.generate().items():
                bitrate = profile.default_bitrate
                bitrate_label = f", {format_bitrate(bitrate)}" if bitrate else ""
                print(f"- {technology_id} ({profile.kind}{bitrate_label})")
        return

    if args.write_config_template is not None:
        from communication_simulator import write_config_template

        write_config_template(args.write_config_template)
        print(f"Konfigurationsvorlage geschrieben: {args.write_config_template.resolve()}")
        return

    interactive_native = False
    if len(sys.argv) == 1:
        cli_mode = choose_mode(
            "Simulationsart:",
            {
                "1": "Technologieoffene Standalone-Simulation (alle registrierten Technologien)",
                "2": "Native CAN/CAN-FD/CAN-XL/Ethernet-Dateiformate",
            },
            default_value="1",
        )
        if cli_mode == "1":
            options = InteractiveStandaloneCli().collect()
            runner = StandaloneCliRunner()
            result = runner.run(options)
            runner.print_result(result)
            return
        interactive_native = True

    if args.technology is not None and not args.native_cli:
        if not 2 <= args.nodes <= 100:
            parser.error("--nodes muss zwischen 2 und 100 liegen")
        if args.duration <= 0:
            parser.error("--duration muss größer als 0 sein")
        if args.cycle_ms <= 0:
            parser.error("--cycle-ms muss größer als 0 sein")
        if args.bitrate is not None and args.bitrate < 1:
            parser.error("--bitrate muss mindestens 1 bit/s sein")
        if args.max_events is not None and args.max_events < 1:
            parser.error("--max-events muss mindestens 1 sein")
        if args.max_events is None and args.messages is not None and args.messages < 1:
            parser.error("--messages muss mindestens 1 sein")
        for name in ("dropout_probability", "corruption_probability"):
            if not 0.0 <= float(getattr(args, name)) <= 1.0:
                parser.error(f"--{name.replace('_', '-')} muss zwischen 0.0 und 1.0 liegen")
        try:
            options = options_from_namespace(args)
            runner = StandaloneCliRunner()
            result = runner.run(options, validate_only=args.validate_only)
        except (OSError, TypeError, ValueError) as exc:
            parser.error(str(exc))
        runner.print_result(result)
        return

    if args.config is not None and not args.native_cli:
        runner = StandaloneCliRunner()
        try:
            result = runner.simulator.run(
                runner.simulator.load_config(args.config),
                validate_only=args.validate_only,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Simulationskonfiguration konnte nicht verarbeitet werden: {exc}")
        runner.print_result(result)
        return

    simulation_config: Dict[str, Any] | None = None
    if args.config is not None:
        try:
            simulation_config = load_simulation_config(args.config)
            apply_simulation_config_to_args(args, simulation_config)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Simulationskonfiguration konnte nicht gelesen werden: {exc}")

    if args.write_routing_template is not None:
        write_routing_template(args.write_routing_template)
        print(f"Routing-Template geschrieben: {args.write_routing_template.resolve()}")
        return

    if args.simulation_mode not in {"existing", "restbus"}:
        parser.error("--simulation-mode muss existing oder restbus sein")
    if args.bus not in {"classic", "fd", "xl"}:
        parser.error("--bus muss classic, fd oder xl sein")
    if not 1 <= int(args.channels) <= 16:
        parser.error("--channels muss zwischen 1 und 16 liegen")

    if interactive_native:
        selected_profile = choice()
        bus_type = str(selected_profile["bus_type"])
        nominal_bitrate = int(selected_profile["nominal_bitrate"])
        data_bitrate_value = selected_profile["data_bitrate"]
        data_bitrate = int(data_bitrate_value) if data_bitrate_value is not None else None
        channel_count = int(selected_profile["channel_count"])
        args.eth_bitrate = selected_profile["eth_bitrate"]
        args.eth_bitrates = selected_profile["eth_bitrates"]
        args.eth_messages = selected_profile["eth_messages"]
        args.formats = str(selected_profile["formats"])
        if selected_profile["out_dir"] is not None:
            args.out_dir = str(selected_profile["out_dir"])
    else:
        bus_type = "classic" if args.classic_can else args.bus
        nominal_bitrate = args.nominal_bitrate
        channel_count = args.channels
        if bus_type == "classic":
            data_bitrate = None
        elif bus_type == "fd":
            data_bitrate = args.fd_bitrate
            if data_bitrate is None:
                data_bitrate = 2_000_000
        else:
            data_bitrate = args.xl_data_bitrate
            if data_bitrate is None:
                data_bitrate = CAN_XL_DATA_BITRATES["e"]
        if bus_type == "fd" and data_bitrate is None:
            data_bitrate = 2_000_000

    restbus_participants: List[RestbusParticipant] | None = None
    restbus_summary: Dict[str, object] | None = None
    if args.routing_table:
        routing_rows = load_routing_table(args.routing_table, channel_count)
    elif args.simulation_mode == "restbus":
        try:
            restbus_participants = restbus_participants_from_request(simulation_config or {}, channel_count)
            requested_routes = int(args.messages) if args.messages is not None else None
            routing_rows = build_restbus_routing_rows(restbus_participants, channel_count, max_routes=requested_routes)
            restbus_summary = restbus_interface_summary(restbus_participants, routing_rows)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        routing_rows = None
    num_messages = args.messages
    if num_messages is None:
        num_messages = len(routing_rows) if routing_rows is not None else 100

    try:
        selected_formats = parse_formats(args.formats)
        args.eth_bitrates = parse_ethernet_bitrates(args.eth_bitrates)
    except ValueError as exc:
        parser.error(str(exc))
    if args.eth_messages is not None and args.eth_messages < 1:
        parser.error("--eth-messages muss mindestens 1 sein")

    legacy_single_output = (
        args.out_dir is None
        and selected_formats == ["blf", "dbc"]
    )

    if not legacy_single_output:
        route_generated_out_dir_to_library(args, selected_formats)
        package_type = package_type_from_formats(selected_formats)
        progress = ProgressBar()
        written, warnings = generate_format_package(
            formats=selected_formats,
            args=args,
            bus_type=bus_type,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            channel_count=channel_count,
            routing_rows=routing_rows,
            num_messages=num_messages,
            progress=progress,
        )
        interface_path = args.interface_out
        if interface_path is None and (args.simulation_mode == "restbus" or args.config is not None):
            interface_path = Path(args.out_dir or "generated_trace_package").resolve() / "simulation_interface.json"
        if interface_path is not None:
            progress.update(97, "Schreibe Simulations-Interface")
            write_simulation_interface(
                interface_path.resolve(),
                simulation_mode=args.simulation_mode,
                written=written,
                warnings=warnings,
                duration_s=args.duration,
                bus_type=bus_type,
                channel_count=channel_count,
                nominal_bitrate=nominal_bitrate,
                data_bitrate=data_bitrate,
                routing_rows=routing_rows,
                restbus_summary=restbus_summary,
                filter_summary=getattr(args, "filter_summary", None),
                signal_suggestions=getattr(args, "signal_suggestions", None),
                hardware_summary=getattr(args, "hardware_summary", None),
                hardware_validation=getattr(args, "hardware_validation", None),
            )
            written.append(interface_path.resolve())
        progress.update(99, "Finalisiere Trace-Ordner")
        trace_package_path = archive_trace_package_to_library(Path(args.out_dir or "generated_trace_package").resolve(), package_type)
        progress.update(100, "Erstellung fertig")
        print("Fertig.")
        print(f"Pakettyp: {package_type.capitalize() if package_type != 'can' else 'CAN'}")
        print(f"Simulation: {args.simulation_mode}")
        print(f"Formate: {', '.join(selected_formats)}")
        if package_type in {"ethernet", "mixed"}:
            selected_eth_bitrates = args.eth_bitrates or [args.eth_bitrate]
            print(f"Ethernet-Geschwindigkeiten: {', '.join(format_bitrate(int(value)) for value in selected_eth_bitrates)}")
            print(f"Ethernet-Kommunikationsströme: {args.eth_messages or num_messages}")
        print(f"Dateien: {len(written)}")
        for path in written:
            print(f"- {path}")
        if args.routing_table:
            print(f"Routing-Tabelle: {args.routing_table.resolve()} ({len(routing_rows)} Routen)")
        elif args.simulation_mode == "restbus":
            print(f"Restbus: {len(restbus_participants or [])} Teilnehmer, {len(routing_rows or [])} Routen")
        if trace_package_path is not None:
            print(f"Trace folder: {trace_package_path}")
        if warnings:
            print("Warnungen:")
            for warning in warnings:
                print(f"- {warning}")
        return

    out_blf = Path(args.out).resolve()
    out_dbc = Path(args.dbc).resolve()

    progress = ProgressBar()
    progress.update(15, "Erzeuge BLF Trace")
    messages = generate_blf(
        out_blf=out_blf,
        duration_s=args.duration,
        bus_type=bus_type,
        seed=args.seed,
        num_messages=num_messages,
        nominal_bitrate=nominal_bitrate,
        data_bitrate=data_bitrate,
        channel_count=channel_count,
        routing_rows=routing_rows,
    )
    progress.update(72, "Schreibe DBC Datenbank")
    write_dbc(out_dbc, messages, nominal_bitrate=nominal_bitrate, data_bitrate=data_bitrate)

    progress.update(85, "Validiere BLF")
    count, first, last = validate_blf(out_blf)
    written = [out_blf, out_dbc]
    interface_path = args.interface_out
    if interface_path is None and (args.simulation_mode == "restbus" or args.config is not None):
        interface_path = out_blf.parent / "simulation_interface.json"
    if interface_path is not None:
        progress.update(95, "Schreibe Simulations-Interface")
        write_simulation_interface(
            interface_path.resolve(),
            simulation_mode=args.simulation_mode,
            written=written,
            warnings=[],
            duration_s=args.duration,
            bus_type=bus_type,
            channel_count=channel_count,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            routing_rows=routing_rows,
            restbus_summary=restbus_summary,
            filter_summary=getattr(args, "filter_summary", None),
            signal_suggestions=getattr(args, "signal_suggestions", None),
            hardware_summary=getattr(args, "hardware_summary", None),
            hardware_validation=getattr(args, "hardware_validation", None),
        )
        written.append(interface_path.resolve())

    progress.update(99, "Aktualisiere Library")
    library_path = archive_generated_files_to_library(written, "can")
    progress.update(100, "Erstellung fertig")
    print("Fertig.")
    print(f"BLF: {out_blf}")
    print(f"DBC: {out_dbc}")
    if interface_path is not None:
        print(f"Simulationsergebnis: {interface_path.resolve()}")
    if library_path is not None:
        print(f"Library: {library_path}")
    print(f"Frames: {count}")
    print(f"UTC-Zeitbereich: {format_utc_timestamp(first)} bis {format_utc_timestamp(last)}")
    print(f"Trace-Dauer: {last - first:.6f}s")
    mode_label = {"classic": "Classic CAN", "fd": "CAN-FD", "xl": "CAN-XL"}[bus_type]
    print(f"Modus: {mode_label}")
    print(f"Nominale Datenrate: {format_bitrate(nominal_bitrate)}")
    if bus_type in {"fd", "xl"}:
        print(f"Datenphase: {format_bitrate(data_bitrate)}")
    if bus_type == "xl":
        print("CAN-XL Hinweis: natives CAN-XL wird von dieser python-can/BLF-Version nicht unterstützt; BLF ist CAN-FD-kompatibel gespeichert.")
    active_channels = sorted({m.channel for m in messages} | {m.gateway_to_channel for m in messages if m.gateway_to_channel is not None})
    print(f"CAN-Kanäle: {channel_count} konfiguriert ({', '.join(f'CAN{ch}' for ch in range(channel_count))})")
    print(f"Aktive Kanäle im Nachrichtenmodell: {', '.join(f'CAN{ch}' for ch in active_channels)}")
    print(f"Simulation: {args.simulation_mode}")
    if args.routing_table:
        print(f"Routing-Tabelle: {args.routing_table.resolve()} ({len(routing_rows)} Routen)")
    elif args.simulation_mode == "restbus":
        print(f"Restbus: {len(restbus_participants or [])} Teilnehmer, {len(routing_rows or [])} Routen")
    print(f"Kommunikation: {len([m for m in messages if m.kind == 'data'])} Datenbotschaften + "
          f"{len([m for m in messages if m.kind == 'response'])} Empfangsantworten")
    print("Hinweis: Jede Datenbotschaft hat eine passende ACK/NACK Response mit CRC-, DLC- und Counter-Prüfung.")


if __name__ == "__main__":
    main()
