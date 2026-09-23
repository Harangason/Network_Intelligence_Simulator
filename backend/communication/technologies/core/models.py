"""Industry-neutral objects separating devices, protocols and payloads."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Layer(StrEnum):
    PHYSICAL = "PHYSICAL"
    DATA_LINK = "DATA_LINK"
    NETWORK = "NETWORK"
    TRANSPORT = "TRANSPORT"
    APPLICATION = "APPLICATION"
    INDUSTRY_PROFILE = "INDUSTRY_PROFILE"


class ImplementationStatus(StrEnum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    PLANNED = "PLANNED"
    EXPERIMENTAL = "EXPERIMENTAL"
    LEGACY = "LEGACY"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class TransportUnitType(StrEnum):
    FRAME = "FRAME"
    MESSAGE = "MESSAGE"
    TELEGRAM = "TELEGRAM"
    PDU = "PDU"
    PACKET = "PACKET"
    WORD = "WORD"
    DATAGRAM = "DATAGRAM"
    TOPIC_SAMPLE = "TOPIC_SAMPLE"
    SERVICE_REQUEST = "SERVICE_REQUEST"
    SERVICE_RESPONSE = "SERVICE_RESPONSE"
    SERVICE_EVENT = "SERVICE_EVENT"
    REGISTER_BLOCK = "REGISTER_BLOCK"
    PROCESS_DATA = "PROCESS_DATA"
    STREAM_CHUNK = "STREAM_CHUNK"
    FILE_BLOCK = "FILE_BLOCK"


class PayloadElementType(StrEnum):
    SIGNAL = "SIGNAL"
    FIELD = "FIELD"
    REGISTER = "REGISTER"
    COIL = "COIL"
    DATA_OBJECT = "DATA_OBJECT"
    ARRAY = "ARRAY"
    STRUCT = "STRUCT"
    OBJECT_LIST = "OBJECT_LIST"
    IMAGE = "IMAGE"
    POINT_CLOUD = "POINT_CLOUD"
    AUDIO = "AUDIO"
    RAW_DATA = "RAW_DATA"
    COMMAND = "COMMAND"
    EVENT = "EVENT"
    QUALITY = "QUALITY"
    STATUS = "STATUS"


def _required(value: str, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


@dataclass(frozen=True)
class HardwareNode:
    id: str
    name: str
    device_type: str
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "id"))
        object.__setattr__(self, "device_type", _required(self.device_type, "device_type"))


@dataclass(frozen=True)
class HardwareInterface:
    id: str
    hardware_node_ref: str
    interface_type: str
    capabilities: tuple[str, ...] = ()
    network_ref: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "id"))
        object.__setattr__(self, "hardware_node_ref", _required(self.hardware_node_ref, "hardware_node_ref"))
        object.__setattr__(self, "interface_type", _required(self.interface_type, "interface_type"))


@dataclass(frozen=True)
class FunctionalInterface:
    id: str
    name: str
    producer_ref: str
    consumer_refs: tuple[str, ...]
    semantic_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "id"))
        object.__setattr__(self, "producer_ref", _required(self.producer_ref, "producer_ref"))
        if not self.consumer_refs:
            raise ValueError("consumer_refs must not be empty")


@dataclass(frozen=True)
class PayloadElement:
    id: str
    element_type: PayloadElementType
    semantic_ref: str
    data_type: str
    size: int
    unit: str | None = None
    encoding: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    source_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "id"))
        if self.size < 0:
            raise ValueError("size must not be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TransportRequirement:
    data_complexity: str = "PHYSICAL_SCALAR"
    bandwidth_bps: int | None = None
    maximum_latency_ms: float | None = None
    maximum_jitter_ms: float | None = None
    deterministic: bool = False
    cyclic: bool = True
    safety: bool = False
    redundancy: bool = False
    topology: str | None = None
    cost_profile: str | None = None


@dataclass(frozen=True)
class TechnologyCapability:
    supports_signals: bool = True
    supports_data_objects: bool = False
    supports_streams: bool = False
    supports_multicast: bool = False
    supports_publish_subscribe: bool = False
    supports_request_response: bool = False
    supports_cyclic: bool = True
    supports_event: bool = True
    supports_redundancy: bool = False
    supports_time_sync: bool = False
    supports_safety_profile: bool = False
    supports_segmentation: bool = False
    supports_fragmentation: bool = False
    supports_qos: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class TechnologyProfile:
    id: str
    layer: Layer
    implementation_status: ImplementationStatus
    rate_model: dict[str, Any]
    mechanisms: dict[str, list[str]]
    physical_layer_profile_id: str | None
    medium_access_model: str | None
    arbitration_model_id: str | None
    definition: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TechnologyProfile:
        definition = deepcopy(raw)
        identifier = _required(definition.get("id"), "id")
        layer = Layer(definition["layer"])
        status = ImplementationStatus(definition["implementation_status"])
        rate_model = definition.get("rate_model") or {}
        if not isinstance(rate_model, dict):
            raise ValueError("rate_model must be an object")
        mechanisms = definition.get("mechanisms") or {}
        if not isinstance(mechanisms, dict):
            raise ValueError("mechanisms must be an object")
        return cls(identifier, layer, status, deepcopy(rate_model), deepcopy(mechanisms),
                   definition.get("physical_layer_profile_id"), definition.get("medium_access_model"),
                   definition.get("arbitration_model_id"), definition)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.definition)


@dataclass(frozen=True)
class TechnologyStack:
    technology_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.technology_ids:
            raise ValueError("technology stack must not be empty")


@dataclass(frozen=True)
class TechnologyBinding:
    id: str
    functional_interface_ref: str
    stack: TechnologyStack
    hardware_interface_ref: str | None = None
    network_ref: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransportUnit:
    id: str
    technology_binding_ref: str
    transport_unit_type: TransportUnitType
    producer_ref: str
    consumer_refs: tuple[str, ...]
    payload_elements: tuple[PayloadElement, ...]
    payload_size: int
    timing: dict[str, Any] = field(default_factory=dict)
    identifier: dict[str, Any] = field(default_factory=dict)
    priority: int | None = None
    qos: dict[str, Any] = field(default_factory=dict)
    status: str = "PROPOSED"
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.payload_size < 0:
            raise ValueError("payload_size must not be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
