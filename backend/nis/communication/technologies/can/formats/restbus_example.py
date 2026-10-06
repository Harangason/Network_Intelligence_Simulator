"""Historical CAN-channel restbus example contract; no project defaults."""
from __future__ import annotations
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from backend.nis.traces.trace_support import safe_identifier, parse_optional_int
from backend.nis.traces.trace_realism import contains_external_signal_records, external_signal_records
from backend.nis.communication.technologies.can.formats.routing import normalized_routing_row
from backend.nis.industries.automotive.templates import trace_example
_example = json.loads(Path(trace_example.__file__).with_name('restbus-example.json').read_text(encoding='utf-8'))
DEFAULT_RESTBUS_PARTICIPANTS = _example['DEFAULT_RESTBUS_PARTICIPANTS']
ROLE_CYCLE_FALLBACK_MS = _example['ROLE_CYCLE_FALLBACK_MS']

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

