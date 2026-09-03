"""Deterministic signal packing and interface allocation helpers.

AI may propose candidate signals, timing and receiver sets. This module performs
the mechanical engineering decisions: payload class selection, atomic signal
placement, frame load estimation and reuse-first interface allocation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import ceil
from typing import Any, Iterable

from .capacity.calculators import estimate_frame, utilization_percent


CAN_FD_PAYLOAD_CLASSES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)


@dataclass(frozen=True)
class SignalCandidate:
    name: str
    required_bits: int
    producer_function_ref: str
    sender_hardware_ref: str
    technology: str = "CAN_FD"
    cycle_ms: float = 10.0
    receiver_set: tuple[str, ...] = ()
    priority: str = "NORMAL"
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.required_bits <= 0:
            raise ValueError("required_bits must be positive.")
        if self.cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive.")


@dataclass
class PackedSignal:
    name: str
    start_bit: int
    length_bits: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PackedMessage:
    name: str
    producer_function_ref: str
    sender_hardware_ref: str
    technology: str
    cycle_ms: float
    receiver_set: tuple[str, ...]
    priority: str
    payload_used_bits: int = 0
    payload_capacity_bits: int = 0
    interface_ref: str | None = None
    network_ref: str | None = None
    load_contribution_percent: float = 0.0
    projected_interface_load_percent: float = 0.0
    signals: list[PackedSignal] = field(default_factory=list)

    @property
    def dlc(self) -> int:
        return self.payload_capacity_bits // 8

    @property
    def payload_free_bits(self) -> int:
        return max(0, self.payload_capacity_bits - self.payload_used_bits)

    @property
    def payload_utilization(self) -> float:
        if self.payload_capacity_bits <= 0:
            return 0.0
        return self.payload_used_bits / self.payload_capacity_bits

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dlc"] = self.dlc
        data["payload_free_bits"] = self.payload_free_bits
        data["payload_utilization"] = round(self.payload_utilization, 4)
        return data


@dataclass(frozen=True)
class HardwareCapability:
    hardware_ref: str
    supported_network_technologies: tuple[str, ...] = ("CAN_FD",)
    max_channels_by_technology: dict[str, int] = field(default_factory=dict)

    def supports(self, technology: str) -> bool:
        normalized = _normalized_technology(technology)
        return normalized in {_normalized_technology(item) for item in self.supported_network_technologies}

    def max_channels(self, technology: str) -> int:
        normalized = _normalized_technology(technology)
        return int(self.max_channels_by_technology.get(normalized, self.max_channels_by_technology.get(technology, 1)) or 1)


@dataclass
class HardwareInterfaceState:
    interface_ref: str
    sender_hardware_ref: str
    technology: str
    network_ref: str
    channel_index: int = 1
    current_load_percent: float = 0.0
    target_load_limit: float = 60.0


@dataclass
class InterfaceAllocationDecision:
    message_name: str
    selected_hardware_interface: str | None
    selected_network: str | None
    projected_network_load: float
    proposal_required: bool = False
    finding: str | None = None


class HardwareInterfaceAllocationService:
    """Assign packed messages to physical interfaces after packing is complete."""

    def __init__(
        self,
        *,
        target_load_percent: float = 60.0,
        parameters: dict[str, Any] | None = None,
        capabilities: dict[str, HardwareCapability] | None = None,
        existing_interfaces: Iterable[HardwareInterfaceState] = (),
    ) -> None:
        self.target_load_percent = target_load_percent
        self.parameters = parameters or {}
        self.capabilities = capabilities or {}
        self.interfaces: dict[tuple[str, str], list[HardwareInterfaceState]] = {}
        for interface in existing_interfaces:
            key = (interface.sender_hardware_ref, _normalized_technology(interface.technology))
            self.interfaces.setdefault(key, []).append(interface)

    def allocate(self, messages: list[PackedMessage]) -> list[InterfaceAllocationDecision]:
        decisions: list[InterfaceAllocationDecision] = []
        for message in messages:
            decisions.append(self.allocate_message(message))
        return decisions

    def allocate_message(self, message: PackedMessage) -> InterfaceAllocationDecision:
        technology = _normalized_technology(message.technology)
        capability = self.capabilities.get(message.sender_hardware_ref)
        if capability and not capability.supports(technology):
            return InterfaceAllocationDecision(
                message_name=message.name,
                selected_hardware_interface=None,
                selected_network=None,
                projected_network_load=0.0,
                proposal_required=True,
                finding="HARDWARE_CAPABILITY_EXCEEDED",
            )
        contribution = _message_load_percent(message, self.parameters)
        key = (message.sender_hardware_ref, technology)
        interfaces = self.interfaces.setdefault(key, [])
        selected = next(
            (
                interface
                for interface in interfaces
                if interface.current_load_percent + contribution <= interface.target_load_limit
            ),
            None,
        )
        if selected is None:
            max_channels = capability.max_channels(technology) if capability else max(len(interfaces) + 1, 1)
            if len(interfaces) >= max_channels:
                return InterfaceAllocationDecision(
                    message_name=message.name,
                    selected_hardware_interface=None,
                    selected_network=None,
                    projected_network_load=round(sum(item.current_load_percent for item in interfaces), 4),
                    proposal_required=True,
                    finding="HARDWARE_CAPABILITY_EXCEEDED",
                )
            selected = HardwareInterfaceState(
                interface_ref=f"{message.sender_hardware_ref}_{len(interfaces) + 1}",
                sender_hardware_ref=message.sender_hardware_ref,
                technology=technology,
                network_ref=f"{technology}_NETWORK_{len(interfaces) + 1}",
                channel_index=len(interfaces) + 1,
                target_load_limit=self.target_load_percent,
            )
            interfaces.append(selected)
        selected.current_load_percent += contribution
        message.interface_ref = selected.interface_ref
        message.network_ref = selected.network_ref
        message.load_contribution_percent = round(contribution, 4)
        message.projected_interface_load_percent = round(selected.current_load_percent, 4)
        return InterfaceAllocationDecision(
            message_name=message.name,
            selected_hardware_interface=selected.interface_ref,
            selected_network=selected.network_ref,
            projected_network_load=message.projected_interface_load_percent,
        )


def valid_payload_bytes(technology: str, required_bytes: int) -> int | None:
    required = max(0, int(ceil(required_bytes)))
    normalized = _normalized_technology(technology)
    if normalized in {"CAN_FD", "CANFD", "CAN_XL"}:
        return next((value for value in CAN_FD_PAYLOAD_CLASSES if value >= required), None)
    if normalized in {"CAN", "LIN"}:
        return max(1, required) if required <= 8 else None
    return max(1, required)


def pack_signals(
    signals: Iterable[SignalCandidate],
    *,
    target_load_percent: float = 60.0,
    parameters: dict[str, Any] | None = None,
) -> list[PackedMessage]:
    grouped: dict[tuple[Any, ...], list[SignalCandidate]] = {}
    for signal in signals:
        receiver_key = tuple(sorted(str(item) for item in signal.receiver_set))
        key = (
            signal.producer_function_ref,
            signal.sender_hardware_ref,
            _normalized_technology(signal.technology),
            signal.cycle_ms,
            receiver_key,
            signal.priority,
        )
        grouped.setdefault(key, []).append(signal)

    messages: list[PackedMessage] = []
    for group in grouped.values():
        group_messages: list[PackedMessage] = []
        for signal in sorted(group, key=lambda item: item.name.lower()):
            max_bits = _max_payload_bytes(signal.technology) * 8
            message = next((item for item in group_messages if item.payload_used_bits + signal.required_bits <= max_bits), None)
            if message is None:
                message = PackedMessage(
                    name=f"{signal.producer_function_ref}Data" if not group_messages else f"{signal.producer_function_ref}Data{len(group_messages) + 1}",
                    producer_function_ref=signal.producer_function_ref,
                    sender_hardware_ref=signal.sender_hardware_ref,
                    technology=signal.technology,
                    cycle_ms=signal.cycle_ms,
                    receiver_set=tuple(sorted(signal.receiver_set)),
                    priority=signal.priority,
                )
                group_messages.append(message)
                messages.append(message)
            start_bit = message.payload_used_bits
            message.signals.append(PackedSignal(signal.name, start_bit, signal.required_bits, signal.data))
            message.payload_used_bits += signal.required_bits
            payload_bytes = valid_payload_bytes(signal.technology, ceil(message.payload_used_bits / 8))
            if payload_bytes is None:
                raise ValueError(f"Signal {signal.name} exceeds one {signal.technology} frame.")
            message.payload_capacity_bits = payload_bytes * 8

    return allocate_messages_to_interfaces(messages, target_load_percent=target_load_percent, parameters=parameters)


def allocate_messages_to_interfaces(
    messages: list[PackedMessage],
    *,
    target_load_percent: float = 60.0,
    parameters: dict[str, Any] | None = None,
) -> list[PackedMessage]:
    HardwareInterfaceAllocationService(
        target_load_percent=target_load_percent,
        parameters=parameters,
    ).allocate(messages)
    return messages


def _message_load_percent(message: PackedMessage, parameters: dict[str, Any]) -> float:
    estimate = estimate_frame(message.technology, message.dlc, parameters)
    return utilization_percent(estimate.transmission_time_s, message.cycle_ms)


def _normalized_technology(value: str) -> str:
    return str(value or "CUSTOM").upper().replace("-", "_").replace(" ", "_")


def _max_payload_bytes(technology: str) -> int:
    normalized = _normalized_technology(technology)
    if normalized in {"CAN_FD", "CANFD", "CAN_XL"}:
        return 64
    if normalized in {"CAN", "LIN"}:
        return 8
    if normalized in {"ETHERNET", "AUTOMOTIVE_ETHERNET", "SOME_IP", "SOMEIP"}:
        return 1400
    return 64
