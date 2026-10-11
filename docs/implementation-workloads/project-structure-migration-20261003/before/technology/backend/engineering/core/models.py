"""Canonical, industry-neutral Engineering Core data contracts.

These dataclasses are intentionally small and persistence-free. They define the
shared vocabulary that Python services can use before API DTOs are rendered for
the frontend.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from ..addressing import LogicalNodeAddress


def _clean_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty.")
    return text


@dataclass(frozen=True)
class EngineeringObject:
    id: str
    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _clean_text(self.id, "id"))
        object.__setattr__(self, "name", _clean_text(self.name, "name"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HardwareNode(EngineeringObject):
    device_type: str = "GenericDevice"
    ports: tuple[str, ...] = ()
    diagnostic_addressable: bool = False
    logical_node_address: LogicalNodeAddress | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "device_type", _clean_text(self.device_type, "device_type"))


@dataclass(frozen=True)
class NetworkInterface(EngineeringObject):
    hardware_node_id: str = ""
    interface_type: str = "Other"
    network_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "hardware_node_id", _clean_text(self.hardware_node_id, "hardware_node_id"))
        object.__setattr__(self, "interface_type", _clean_text(self.interface_type, "interface_type"))


@dataclass(frozen=True)
class Network(EngineeringObject):
    technology_id: str = "custom"
    interface_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "technology_id", _clean_text(self.technology_id, "technology_id"))


@dataclass(frozen=True)
class ValueDomain:
    minimum: float | None = None
    maximum: float | None = None
    resolution: float | None = None
    allowed_values: tuple[Any, ...] = ()
    enum_values: dict[str, Any] = field(default_factory=dict)
    reserved_values: tuple[Any, ...] = ()
    invalid_values: tuple[Any, ...] = ()
    default_value: Any = None

    def __post_init__(self) -> None:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not be greater than maximum.")
        if self.resolution is not None and self.resolution <= 0:
            raise ValueError("resolution must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Encoding:
    bit_length: int | None = None
    start_bit: int | None = None
    byte_order: str = "little_endian"
    data_type: str = "unsigned"
    factor: float | None = None
    offset: float | None = None
    encoding_type: str = "linear"

    def __post_init__(self) -> None:
        if self.bit_length is not None and self.bit_length <= 0:
            raise ValueError("bit_length must be positive.")
        if self.start_bit is not None and self.start_bit < 0:
            raise ValueError("start_bit must not be negative.")
        if self.byte_order not in {"little_endian", "big_endian"}:
            raise ValueError("byte_order must be little_endian or big_endian.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProtocolBinding:
    protocol_id: str
    network_id: str | None = None
    message_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_id", _clean_text(self.protocol_id, "protocol_id"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConnectionType(StrEnum):
    DIRECT_IO = "DIRECT_IO"
    COMMUNICATION_TECHNOLOGY = "COMMUNICATION_TECHNOLOGY"


@dataclass(frozen=True)
class DirectSignalBinding:
    """A canonical Signal's physical conductor; stored in Signal.configuration."""

    source_hardware_node_ref: str
    destination_hardware_node_ref: str | None
    physical_port_ref: str
    signal_type: str
    electrical_profile: dict[str, Any] = field(default_factory=dict)
    update_rate_hz: float | None = None
    timing_profile: dict[str, Any] = field(default_factory=dict)
    validation_status: str = "REVIEW_REQUIRED"

    def __post_init__(self) -> None:
        for key in ("source_hardware_node_ref", "physical_port_ref", "signal_type"):
            if not str(getattr(self, key) or "").strip():
                raise ValueError(f"DirectSignalBinding.{key} is required")
        if self.update_rate_hz is not None and self.update_rate_hz <= 0:
            raise ValueError("DirectSignalBinding.update_rate_hz must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Signal(EngineeringObject):
    semantic_type: str = "UNKNOWN"
    value_domain: ValueDomain = field(default_factory=ValueDomain)
    encoding: Encoding = field(default_factory=Encoding)
    protocol_binding: ProtocolBinding | None = None
    direct_signal_binding: DirectSignalBinding | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "semantic_type", _clean_text(self.semantic_type, "semantic_type").upper())
        if self.protocol_binding and self.direct_signal_binding:
            raise ValueError("Signal cannot have both protocol and direct I/O bindings")


@dataclass(frozen=True)
class Message(EngineeringObject):
    interface_id: str | None = None
    dlc: int | None = None
    signal_ids: tuple[str, ...] = ()
    cycle_ms: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.dlc is not None and self.dlc < 0:
            raise ValueError("dlc must not be negative.")
        if self.cycle_ms is not None and self.cycle_ms <= 0:
            raise ValueError("cycle_ms must be positive.")


@dataclass(frozen=True)
class RouteHop:
    node_id: str
    interface_id: str | None = None
    network_id: str | None = None
    protocol_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _clean_text(self.node_id, "node_id"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Route(EngineeringObject):
    source: RouteHop = field(default_factory=lambda: RouteHop("source"))
    destinations: tuple[RouteHop, ...] = ()
    message_ids: tuple[str, ...] = ()
    signal_ids: tuple[str, ...] = ()
    policy: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.destinations:
            raise ValueError("route destinations must not be empty.")
