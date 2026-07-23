#!/usr/bin/env python3
"""Shared trace model for the format generator scripts.

The module deliberately uses only the Python standard library so the text,
XML, JSON, CSV, PCAP, and PCAPNG generators work without optional packages.
BLF and MDF/MF4 stay in their dedicated scripts because they depend on
external format libraries.
"""

from __future__ import annotations

import random
import csv
import re
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trace_realism import external_signal_records, physical_raw_value, signal_specs_for_message


ROUTE_INFO_START_BYTE = 20
ROUTE_INFO_LENGTH = 44

COMMUNICATION_PAIRS = [
    ("LIDAR_FRONT", "ADAS_DOMAIN", 20),
    ("CAMERA_FRONT_WIDE", "ADAS_DOMAIN", 33),
    ("RADAR_FRONT_LONG_RANGE", "ADAS_DOMAIN", 20),
    ("RADAR_REAR_CROSS_TRAFFIC", "ADAS_DOMAIN", 50),
    ("ULTRASONIC_LEFT_CLUSTER", "PARK_ASSIST", 40),
    ("ULTRASONIC_RIGHT_CLUSTER", "PARK_ASSIST", 40),
    ("IMU_YAW_RATE_SENSOR", "ADAS_DOMAIN", 10),
    ("WHEEL_SPEED_FRONT_LEFT", "BRAKE_CONTROLLER", 10),
    ("BRAKE_CONTROLLER", "ADAS_DOMAIN", 20),
    ("ADAS_DOMAIN", "VEHICLE_MOTION_CONTROLLER", 20),
]

DEFAULT_ROUTING_ROWS = [
    {"name": "LIDAR_OBJECT_LIST", "sender": "LIDAR_FRONT", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 0, "gateway_to_channel": 1, "frame_id": 0x100},
    {"name": "CAMERA_LANE_MODEL", "sender": "CAMERA_FRONT_WIDE", "receiver": "ADAS_DOMAIN", "cycle_ms": 33, "channel": 1, "gateway_to_channel": "", "frame_id": 0x101},
    {"name": "RADAR_TARGET_LIST", "sender": "RADAR_FRONT_LONG_RANGE", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 2, "gateway_to_channel": "", "frame_id": 0x102},
    {"name": "REAR_CROSS_TRAFFIC", "sender": "RADAR_REAR_CROSS_TRAFFIC", "receiver": "ADAS_DOMAIN", "cycle_ms": 50, "channel": 3, "gateway_to_channel": "", "frame_id": 0x103},
    {"name": "ULTRASONIC_LEFT_DISTANCE", "sender": "ULTRASONIC_LEFT_CLUSTER", "receiver": "PARK_ASSIST", "cycle_ms": 40, "channel": 4, "gateway_to_channel": "", "frame_id": 0x104},
    {"name": "ULTRASONIC_RIGHT_DISTANCE", "sender": "ULTRASONIC_RIGHT_CLUSTER", "receiver": "PARK_ASSIST", "cycle_ms": 40, "channel": 5, "gateway_to_channel": "", "frame_id": 0x105},
    {"name": "IMU_DYNAMICS", "sender": "IMU_YAW_RATE_SENSOR", "receiver": "ADAS_DOMAIN", "cycle_ms": 10, "channel": 6, "gateway_to_channel": "", "frame_id": 0x106},
    {"name": "WHEEL_SPEED_FL", "sender": "WHEEL_SPEED_FRONT_LEFT", "receiver": "BRAKE_CONTROLLER", "cycle_ms": 10, "channel": 7, "gateway_to_channel": "", "frame_id": 0x107},
    {"name": "BRAKE_STATUS", "sender": "BRAKE_CONTROLLER", "receiver": "ADAS_DOMAIN", "cycle_ms": 20, "channel": 8, "gateway_to_channel": "", "frame_id": 0x108},
    {"name": "ADAS_MOTION_REQUEST", "sender": "ADAS_DOMAIN", "receiver": "VEHICLE_MOTION_CONTROLLER", "cycle_ms": 20, "channel": 9, "gateway_to_channel": "", "frame_id": 0x109},
]

ETHERNET_NODES = {
    "LIDAR_FRONT": ("02:00:00:00:10:01", "192.168.10.11"),
    "CAMERA_FRONT_WIDE": ("02:00:00:00:10:02", "192.168.10.12"),
    "RADAR_FRONT_LONG_RANGE": ("02:00:00:00:10:03", "192.168.10.13"),
    "CENTRAL_GATEWAY": ("02:00:00:00:15:01", "192.168.15.1"),
    "ADAS_DOMAIN": ("02:00:00:00:20:01", "192.168.20.10"),
    "VEHICLE_MOTION_CONTROLLER": ("02:00:00:00:30:01", "192.168.30.10"),
}

SOMEIP_SD_SERVICE_ID = 0xFFFF
SOMEIP_SD_METHOD_ID = 0x8100
SOMEIP_REQUEST = 0x00
SOMEIP_REQUEST_NO_RETURN = 0x01
SOMEIP_NOTIFICATION = 0x02
SOMEIP_RESPONSE = 0x80


@dataclass(frozen=True)
class SignalDef:
    name: str
    start_bit: int
    length: int
    factor: float = 1.0
    offset: float = 0.0
    minimum: int = 0
    maximum: int = 255
    unit: str = ""
    kind: str = "normal"


@dataclass(frozen=True)
class MessageDef:
    name: str
    frame_id: int
    sender: str
    receiver: str
    cycle_ms: int
    channel: int
    dlc: int
    bus_type: str
    kind: str = "data"
    response_for: int | None = None
    gateway_to_channel: int | None = None
    signals: tuple[SignalDef, ...] = ()


@dataclass(frozen=True)
class CanFrame:
    timestamp: float
    rel_time: float
    channel: int
    arbitration_id: int
    name: str
    sender: str
    receiver: str
    data: bytes
    dlc: int
    bus_type: str
    direction: str
    is_fd: bool
    bitrate_switch: bool
    message_kind: str


@dataclass(frozen=True)
class EthernetFrame:
    timestamp: float
    rel_time: float
    src_node: str
    dst_node: str
    src_mac: str
    dst_mac: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    service_id: int
    method_id: int
    message_type: int
    payload: bytes


def utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def route_label(sender: str, receiver: str) -> str:
    return f"{sender} -> {receiver}"


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


def normalize_routing_row(row: dict[str, object], index: int, channels: int) -> dict[str, object]:
    sender = safe_identifier(str(row.get("sender") or row.get("source") or row.get("src") or f"ECU_{index:02d}"), "ECU")
    receiver = safe_identifier(str(row.get("receiver") or row.get("destination") or row.get("dst") or row.get("target") or "ADAS_DOMAIN"), "ECU")
    cycle_ms = parse_optional_int(row.get("cycle_ms") or row.get("cycle") or row.get("period_ms"), 20)
    channel = parse_optional_int(row.get("channel"), index % channels)
    channel = max(0, min(channels - 1, channel if channel is not None else index % channels))
    gateway_to_channel = parse_optional_int(row.get("gateway_to_channel") or row.get("gateway") or row.get("gw_channel"), None)
    if gateway_to_channel is not None:
        gateway_to_channel = max(0, min(channels - 1, gateway_to_channel))
    frame_id = parse_optional_int(row.get("frame_id") or row.get("id") or row.get("can_id"), 0x100 + index)
    name = safe_identifier(str(row.get("name") or row.get("message") or row.get("message_name") or f"{sender}_TO_{receiver}"), "MSG")
    normalized = {
        "name": name,
        "sender": sender,
        "receiver": receiver,
        "cycle_ms": cycle_ms if cycle_ms and cycle_ms > 0 else 20,
        "channel": channel,
        "gateway_to_channel": gateway_to_channel,
        "frame_id": frame_id if frame_id is not None else 0x100 + index,
    }
    route_signals = external_signal_records(row.get("signals") or row.get("signal_definitions") or row.get("message_signals"))
    if route_signals:
        normalized["signals"] = route_signals
        normalized["signal_source"] = str(row.get("signal_source") or "external")
    return normalized


def load_routing_table(path: Path, channels: int) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Routing table is empty: {path}")
    return [normalize_routing_row(row, index, channels) for index, row in enumerate(rows)]


def write_routing_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["name", "sender", "receiver", "cycle_ms", "channel", "gateway_to_channel", "frame_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in DEFAULT_ROUTING_ROWS:
            output = dict(row)
            output["frame_id"] = f"0x{int(output['frame_id']):X}"
            writer.writerow(output)


def crc8_autosar(data: bytes, start_value: int = 0xFF, final_xor: int = 0xFF) -> int:
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
    value &= (1 << length) - 1
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        if byte_index >= len(payload):
            return
        bit_index = absolute_bit % 8
        if value & (1 << bit):
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def get_unsigned_le(payload: bytes, start_bit: int, length: int) -> int:
    value = 0
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        if byte_index >= len(payload):
            return value
        bit_index = absolute_bit % 8
        if payload[byte_index] & (1 << bit_index):
            value |= 1 << bit
    return value


def triangle_wave(t_s: float, period_s: float, minimum: int, maximum: int) -> int:
    if period_s <= 0:
        return minimum
    phase = (t_s % period_s) / period_s
    y = phase * 2.0 if phase < 0.5 else (1.0 - phase) * 2.0
    return int(minimum + y * (maximum - minimum))


def data_signals(
    dlc: int,
    is_fd: bool,
    sender: str = "",
    receiver: str = "",
    message_name: str = "",
    external_signals: list[dict[str, object]] | None = None,
) -> tuple[SignalDef, ...]:
    external_records = external_signal_records(external_signals)
    if external_records:
        return tuple(
            SignalDef(
                record["name"],
                record["start_bit"],
                record["length"],
                record["factor"],
                record["offset"],
                record["minimum"],
                record["maximum"],
                record["unit"],
                record["kind"],
            )
            for record in external_records
        )

    signals: list[SignalDef] = [
        SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"),
        SignalDef("AliveCounter", 8, 4, 1, 0, 0, 15, "", "counter"),
        SignalDef("MuxState", 12, 4, 1, 0, 0, 15, "", "mux"),
    ]
    bit = 16
    signal_count = 12 if is_fd else 6
    length = 12 if is_fd else 8
    signal_specs = signal_specs_for_message(sender, receiver, message_name, signal_count, length)
    for spec in signal_specs:
        if bit + length > dlc * 8:
            break
        signals.append(
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

    if is_fd:
        for idx in range(ROUTE_INFO_LENGTH):
            signals.append(
                SignalDef(
                    name=f"RouteInfoChar_{idx:02d}",
                    start_bit=(ROUTE_INFO_START_BYTE + idx) * 8,
                    length=8,
                    unit="ascii",
                    kind="route_info",
                )
            )
    return tuple(signals)


def response_signals(dlc: int) -> tuple[SignalDef, ...]:
    signals: list[SignalDef] = [
        SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"),
        SignalDef("ResponseCounter", 8, 4, 1, 0, 0, 15, "", "counter"),
        SignalDef("AckState", 12, 4, 1, 0, 0, 15, "", "ack"),
        SignalDef("ReceivedFrameId", 16, 11, 1, 0, 0, 2047, "", "diag"),
        SignalDef("ReceivedCounter", 27, 4, 1, 0, 0, 15, "", "diag"),
        SignalDef("ChecksumOk", 31, 1, 0, 0, 0, 1, "", "diag"),
        SignalDef("PayloadLength", 32, 8, 1, 0, 0, 64, "byte", "diag"),
        SignalDef("ErrorCode", 40, 8, 1, 0, 0, 255, "", "diag"),
        SignalDef("ProcessingTimeUs", 48, 16, 1, 0, 0, 65535, "us", "diag"),
    ]
    if dlc > 8:
        signals.extend(
            [
                SignalDef("ResponseSequence", 64, 16, 1, 0, 0, 65535, "", "diag"),
                SignalDef("ReceivedCrc", 80, 8, 1, 0, 0, 255, "", "diag"),
                SignalDef("CalculatedCrc", 88, 8, 1, 0, 0, 255, "", "diag"),
            ]
        )
    return tuple(signals)


def build_messages(num_messages: int, bus_type: str, channels: int, routing_rows: list[dict[str, object]] | None = None) -> list[MessageDef]:
    channels = max(1, min(16, channels))
    is_fd_storage = bus_type in {"fd", "xl"}
    data_dlc = 64 if is_fd_storage else 8
    response_dlc = 16 if is_fd_storage else 8
    routing_rows = routing_rows or [normalize_routing_row(row, index, channels) for index, row in enumerate(DEFAULT_ROUTING_ROWS)]
    messages: list[MessageDef] = []

    for index in range(num_messages):
        route = routing_rows[index % len(routing_rows)]
        sender = str(route["sender"])
        receiver = str(route["receiver"])
        cycle_ms = int(route["cycle_ms"])
        channel = int(route["channel"])
        gateway_to_channel = route["gateway_to_channel"]
        frame_id = int(route["frame_id"]) + (index // len(routing_rows)) * 0x20
        base_name = str(route["name"])
        messages.append(
            MessageDef(
                name=f"DATA_{index:03d}_{base_name}",
                frame_id=frame_id,
                sender=sender,
                receiver=receiver,
                cycle_ms=cycle_ms,
                channel=channel,
                dlc=data_dlc,
                bus_type=bus_type,
                kind="data",
                gateway_to_channel=int(gateway_to_channel) if gateway_to_channel is not None else None,
                signals=data_signals(data_dlc, is_fd_storage, sender, receiver, base_name, route.get("signals")),
            )
        )
        messages.append(
            MessageDef(
                name=f"RESP_{index:03d}_{receiver}_TO_{sender}",
                frame_id=0x600 + index,
                sender=receiver,
                receiver=sender,
                cycle_ms=cycle_ms,
                channel=channel,
                dlc=response_dlc,
                bus_type=bus_type,
                kind="response",
                response_for=frame_id,
                signals=response_signals(response_dlc),
            )
        )
    return messages


def encode_data_payload(msg: MessageDef, rel_time: float, counter: int, filter_bank: Any | None = None) -> bytes:
    payload = bytearray(((msg.frame_id + int(rel_time * 1000.0) + counter * 31 + idx * 17) & 0xFF) for idx in range(msg.dlc))
    set_unsigned_le(payload, 8, 4, counter & 0xF)
    set_unsigned_le(payload, 12, 4, int((rel_time * 10) % 16) & 0xF)
    physical_index = 0
    for sig in msg.signals:
        if sig.kind in {"crc", "counter", "mux", "route_info"}:
            continue
        value = physical_raw_value(
            signal_name=sig.name,
            factor=sig.factor,
            offset=sig.offset,
            minimum=sig.minimum,
            maximum=sig.maximum,
            timestamp_s=rel_time,
            frame_id=msg.frame_id,
            signal_index=physical_index,
        )
        if filter_bank is not None:
            value = filter_bank.filter_value(
                signal_name=sig.name,
                sender=msg.sender,
                receiver=msg.receiver,
                role=None,
                timestamp_s=rel_time,
                measurement=value,
                minimum=sig.minimum,
                maximum=sig.maximum,
            )
        physical_index += 1
        set_unsigned_le(payload, sig.start_bit, sig.length, value)

    if any(sig.kind == "route_info" for sig in msg.signals) and msg.dlc >= ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH:
        route = route_label(msg.sender, msg.receiver).encode("ascii", errors="replace")
        payload[ROUTE_INFO_START_BYTE : ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH] = route[:ROUTE_INFO_LENGTH].ljust(ROUTE_INFO_LENGTH, b"\x00")

    has_payload_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in msg.signals)
    if has_payload_crc:
        set_unsigned_le(payload, 0, 8, crc8_autosar(bytes(payload[1:])))
    return bytes(payload)


def encode_response_payload(response: MessageDef, request: MessageDef, request_payload: bytes, counter: int, processing_us: int) -> bytes:
    payload = bytearray(((response.frame_id + counter * 19 + idx * 23) & 0xFF) for idx in range(response.dlc))
    received_crc = request_payload[0] if request_payload else 0
    calculated_crc = crc8_autosar(request_payload[1:]) if len(request_payload) >= 2 else 0
    has_request_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in request.signals)
    has_request_counter = any("counter" in sig.kind.lower() or "counter" in sig.name.lower() for sig in request.signals)
    checksum_ok = int((not has_request_crc) or (received_crc == calculated_crc and len(request_payload) >= 2))
    dlc_ok = int(len(request_payload) == request.dlc)
    received_counter = get_unsigned_le(request_payload, 8, 4) if len(request_payload) > 1 else 0
    counter_ok = int((not has_request_counter) or received_counter == (counter & 0xF))
    error_code = (0 if checksum_ok else 0x01) | (0 if dlc_ok else 0x02) | (0 if counter_ok else 0x04)
    ack_state = 1 if error_code == 0 else (2 if error_code & 0x01 else 3 if error_code & 0x02 else 4)

    set_unsigned_le(payload, 8, 4, counter & 0xF)
    set_unsigned_le(payload, 12, 4, ack_state)
    set_unsigned_le(payload, 16, 11, request.frame_id)
    set_unsigned_le(payload, 27, 4, received_counter)
    set_unsigned_le(payload, 31, 1, checksum_ok)
    set_unsigned_le(payload, 32, 8, len(request_payload))
    set_unsigned_le(payload, 40, 8, error_code)
    set_unsigned_le(payload, 48, 16, processing_us)
    if response.dlc > 8:
        set_unsigned_le(payload, 64, 16, counter)
        set_unsigned_le(payload, 80, 8, received_crc)
        set_unsigned_le(payload, 88, 8, calculated_crc)
    set_unsigned_le(payload, 0, 8, crc8_autosar(bytes(payload[1:])))
    return bytes(payload)


def iter_schedule(data_messages: Iterable[MessageDef], duration: float, rng: random.Random) -> Iterable[tuple[float, MessageDef]]:
    for msg in data_messages:
        rel_time = 0.0
        while rel_time <= duration:
            yield max(0.0, rel_time + rng.uniform(-0.0004, 0.0008)), msg
            rel_time += msg.cycle_ms / 1000.0


def build_can_trace(
    duration: float = 1.0,
    messages: int = 10,
    channels: int = 2,
    bus_type: str = "fd",
    seed: int = 42,
    start_utc: float | None = None,
    routing_rows: list[dict[str, object]] | None = None,
    filter_bank: Any | None = None,
) -> tuple[list[MessageDef], list[CanFrame]]:
    rng = random.Random(seed)
    start_utc = utc_now() if start_utc is None else start_utc
    msg_defs = build_messages(messages, bus_type, channels, routing_rows=routing_rows)
    data_messages = [msg for msg in msg_defs if msg.kind == "data"]
    response_by_request = {msg.response_for: msg for msg in msg_defs if msg.kind == "response"}
    alive = {msg.frame_id: 0 for msg in msg_defs}
    events = sorted(iter_schedule(data_messages, duration, rng), key=lambda item: item[0])
    frames: list[CanFrame] = []
    is_fd = bus_type in {"fd", "xl"}

    def control_frame(rel_time: float, channel: int, arbitration_id: int, name: str, sender: str, receiver: str, phase: str, payload_text: str) -> None:
        payload = bytearray(64 if is_fd else 8)
        encoded = payload_text.encode("ascii", errors="replace")[: len(payload) - 1]
        payload[1 : 1 + len(encoded)] = encoded
        payload[0] = crc8_autosar(bytes(payload[1:]))
        frames.append(
            CanFrame(
                start_utc + rel_time,
                rel_time,
                channel,
                arbitration_id,
                name,
                sender,
                receiver,
                bytes(payload),
                len(payload),
                bus_type,
                "Tx",
                is_fd,
                is_fd,
                phase,
            )
        )

    routed_routes = [msg for msg in data_messages if msg.gateway_to_channel is not None]
    for index, msg in enumerate(routed_routes[:8]):
        base = 0.002 + index * 0.006
        control_frame(base, msg.channel, 0x080 + index, f"NM_WAKE_{msg.sender}", msg.sender, "CENTRAL_GATEWAY", "startup", f"NM_WAKE {msg.sender}")
        control_frame(base + 0.0015, msg.channel, 0x0A0 + index, f"GW_ROUTE_OPEN_{msg.sender}", "CENTRAL_GATEWAY", msg.receiver, "gateway_setup", f"ROUTE_OPEN {msg.sender}->{msg.receiver}")
        control_frame(base + 0.0030, msg.channel, 0x0C0 + index, f"CONNECT_REQ_{msg.sender}", msg.sender, msg.receiver, "connect_request", f"CONNECT {msg.sender}->{msg.receiver}")
        control_frame(base + 0.0045, msg.channel, 0x0E0 + index, f"CONNECT_ACK_{msg.receiver}", msg.receiver, msg.sender, "connect_ack", f"ACK CONNECT {msg.receiver}")

    for rel_time, msg in events:
        payload = encode_data_payload(msg, rel_time, alive[msg.frame_id], filter_bank=filter_bank)
        abs_time = start_utc + rel_time
        frames.append(
            CanFrame(abs_time, rel_time, msg.channel, msg.frame_id, msg.name, msg.sender, msg.receiver, payload, len(payload), bus_type, "Tx", is_fd, is_fd, msg.kind)
        )

        response = response_by_request.get(msg.frame_id)
        if response:
            processing_us = rng.randint(350, 1800)
            response_payload = encode_response_payload(response, msg, payload, alive[msg.frame_id], processing_us)
            response_rel_time = rel_time + processing_us / 1_000_000.0
            frames.append(
                CanFrame(
                    start_utc + response_rel_time,
                    response_rel_time,
                    response.channel,
                    response.frame_id,
                    response.name,
                    response.sender,
                    response.receiver,
                    response_payload,
                    len(response_payload),
                    bus_type,
                    "Rx",
                    is_fd,
                    is_fd,
                    response.kind,
                )
            )
            alive[response.frame_id] = (alive[response.frame_id] + 1) & 0xF

        if msg.gateway_to_channel is not None:
            gateway_payload = bytearray(payload)
            if any(sig.kind == "route_info" for sig in msg.signals) and len(gateway_payload) > 1:
                gateway_payload[1] ^= 0x80
            gateway_rel_time = rel_time + rng.uniform(0.001, 0.004)
            frames.append(
                CanFrame(
                    start_utc + gateway_rel_time,
                    gateway_rel_time,
                    msg.gateway_to_channel,
                    0x500 + (msg.frame_id & 0xFF),
                    f"GW_{msg.name}",
                    msg.sender,
                    msg.receiver,
                    bytes(gateway_payload),
                    len(gateway_payload),
                    bus_type,
                    "Tx",
                    is_fd,
                    is_fd,
                    "gateway",
                )
            )
        alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF

    return msg_defs, sorted(frames, key=lambda frame: frame.timestamp)


def mac_bytes(mac: str) -> bytes:
    return bytes(int(part, 16) for part in mac.split(":"))


def ip_bytes(ip: str) -> bytes:
    return bytes(int(part) for part in ip.split("."))


def internet_checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def build_someip_payload(service_id: int, method_id: int, client_id: int, session_id: int, message_type: int, payload: bytes) -> bytes:
    length = 8 + len(payload)
    return struct.pack("!HHIHHBBBB", service_id, method_id, length, client_id, session_id, 1, 1, message_type, 0) + payload


def build_udp_ipv4_ethernet_packet(frame: EthernetFrame) -> bytes:
    udp_payload = build_someip_payload(frame.service_id, frame.method_id, 0x1001, int(frame.rel_time * 1000) & 0xFFFF, frame.message_type, frame.payload)
    udp_len = 8 + len(udp_payload)
    ip_total_len = 20 + udp_len
    identification = int(frame.rel_time * 1000) & 0xFFFF
    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        ip_total_len,
        identification,
        0x4000,
        64,
        17,
        0,
        ip_bytes(frame.src_ip),
        ip_bytes(frame.dst_ip),
    )
    ip_header = ip_header[:10] + struct.pack("!H", internet_checksum(ip_header)) + ip_header[12:]
    pseudo_header = ip_bytes(frame.src_ip) + ip_bytes(frame.dst_ip) + struct.pack("!BBH", 0, 17, udp_len)
    udp_header = struct.pack("!HHHH", frame.src_port, frame.dst_port, udp_len, 0)
    udp_checksum = internet_checksum(pseudo_header + udp_header + udp_payload)
    udp_header = struct.pack("!HHHH", frame.src_port, frame.dst_port, udp_len, udp_checksum)
    return mac_bytes(frame.dst_mac) + mac_bytes(frame.src_mac) + struct.pack("!H", 0x0800) + ip_header + udp_header + udp_payload


def someip_payload_text(kind: str, src_node: str, dst_node: str, service_id: int, sequence: int) -> bytes:
    if kind == "sd_offer":
        return f"SD OFFER service=0x{service_id:04X} provider={src_node}".encode("ascii")
    if kind == "sd_find":
        return f"SD FIND service=0x{service_id:04X} consumer={src_node}".encode("ascii")
    if kind == "subscribe":
        return f"SUBSCRIBE eventgroup=0x0001 service=0x{service_id:04X}".encode("ascii")
    if kind == "subscribe_ack":
        return f"SUBSCRIBE_ACK eventgroup=0x0001 service=0x{service_id:04X}".encode("ascii")
    if src_node == "LIDAR_FRONT":
        objects = []
        for obj_id in range(1, 5):
            x_cm = 1200 + sequence * 7 + obj_id * 135
            y_cm = -180 + obj_id * 95
            vx_cms = -60 + obj_id * 12
            confidence = 82 + (sequence + obj_id) % 15
            objects.append(f"id={obj_id},x_cm={x_cm},y_cm={y_cm},vx_cms={vx_cms},class=vehicle,conf={confidence}")
        return ("LIDAR_OBJECT_LIST ts_ms=%d " % sequence + ";".join(objects)).encode("ascii")
    if src_node == "CAMERA_FRONT_WIDE":
        return f"CAMERA_LANE_MODEL ts_ms={sequence} left_q=91 right_q=88 curvature=0.0012 objects=3".encode("ascii")
    if src_node == "RADAR_FRONT_LONG_RANGE":
        return f"RADAR_TARGET_LIST ts_ms={sequence} tracks=6 range_m=42.3 range_rate_mps=-2.1 azimuth_deg=1.8".encode("ascii")
    return f"{route_label(src_node, dst_node)} seq={sequence} service=0x{service_id:04X}".encode("ascii")


def make_ethernet_frame(
    start_utc: float,
    rel_time: float,
    src_node: str,
    dst_node: str,
    src_port: int,
    dst_port: int,
    service_id: int,
    method_id: int,
    message_type: int,
    payload: bytes,
) -> EthernetFrame:
    src_mac, src_ip = ETHERNET_NODES[src_node]
    dst_mac, dst_ip = ETHERNET_NODES[dst_node]
    return EthernetFrame(
        timestamp=start_utc + rel_time,
        rel_time=rel_time,
        src_node=src_node,
        dst_node=dst_node,
        src_mac=src_mac,
        dst_mac=dst_mac,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        service_id=service_id,
        method_id=method_id,
        message_type=message_type,
        payload=payload,
    )


def build_ethernet_trace(duration: float = 1.0, messages: int = 10, seed: int = 42, start_utc: float | None = None) -> list[EthernetFrame]:
    rng = random.Random(seed)
    start_utc = utc_now() if start_utc is None else start_utc
    endpoints = [
        ("LIDAR_FRONT", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 20, 0x1234, 0x0421),
        ("CAMERA_FRONT_WIDE", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 33, 0x1235, 0x0422),
        ("RADAR_FRONT_LONG_RANGE", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 20, 0x1236, 0x0423),
        ("ADAS_DOMAIN", "CENTRAL_GATEWAY", "VEHICLE_MOTION_CONTROLLER", 20, 0x2234, 0x0101),
    ]
    frames: list[EthernetFrame] = []
    for index in range(messages):
        src_node, gateway_node, dst_node, cycle_ms, service_id, method_id = endpoints[index % len(endpoints)]
        base = 0.001 + index * 0.015
        src_port = 30500 + index
        dst_port = 30490
        frames.extend(
            [
                make_ethernet_frame(start_utc, base, src_node, gateway_node, src_port, dst_port, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_NOTIFICATION, someip_payload_text("sd_offer", src_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.001, dst_node, gateway_node, src_port + 100, dst_port, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_REQUEST, someip_payload_text("sd_find", dst_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.002, gateway_node, dst_node, dst_port, src_port + 100, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_NOTIFICATION, someip_payload_text("sd_offer", gateway_node, dst_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.003, dst_node, gateway_node, src_port + 100, dst_port, service_id, method_id, SOMEIP_REQUEST, someip_payload_text("subscribe", dst_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.004, gateway_node, dst_node, dst_port, src_port + 100, service_id, method_id, SOMEIP_RESPONSE, someip_payload_text("subscribe_ack", gateway_node, dst_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.005, src_node, gateway_node, src_port, dst_port, service_id, method_id, SOMEIP_REQUEST, f"CONNECT_REQ {src_node}->{dst_node}".encode("ascii")),
                make_ethernet_frame(start_utc, base + 0.006, gateway_node, src_node, dst_port, src_port, service_id, method_id, SOMEIP_RESPONSE, f"CONNECT_ACK route={src_node}->{dst_node}".encode("ascii")),
            ]
        )
        rel_time = base + 0.010
        while rel_time <= duration:
            jittered = max(0.0, rel_time + rng.uniform(-0.0002, 0.0005))
            sequence = int(jittered * 1000)
            sensor_payload = someip_payload_text("notification", src_node, dst_node, service_id, sequence)
            frames.append(make_ethernet_frame(start_utc, jittered, src_node, gateway_node, src_port, dst_port, service_id, method_id, SOMEIP_NOTIFICATION, sensor_payload))
            frames.append(make_ethernet_frame(start_utc, jittered + rng.uniform(0.0008, 0.0018), gateway_node, dst_node, dst_port, src_port + 100, service_id, method_id, SOMEIP_NOTIFICATION, sensor_payload + b";gw=forwarded"))
            if int(sequence / max(1, cycle_ms)) % 10 == 0:
                frames.append(make_ethernet_frame(start_utc, jittered + rng.uniform(0.0020, 0.0035), dst_node, gateway_node, src_port + 100, dst_port, service_id, method_id, SOMEIP_RESPONSE, f"APP_ACK service=0x{service_id:04X} seq={sequence}".encode("ascii")))
            rel_time += cycle_ms / 1000.0
    return sorted(frames, key=lambda frame: frame.timestamp)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
