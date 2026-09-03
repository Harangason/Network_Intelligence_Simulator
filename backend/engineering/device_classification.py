"""Device-class registry for HardwareNode classification and generator policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEVICE_CLASSES = {
    0: "Passive",
    1: "Basic",
    2: "Smart / Controlled",
    3: "Perception / Intelligent",
    4: "Intelligent Subsystem",
}

DEVICE_TYPINGS_BY_CLASS: dict[int, tuple[str, ...]] = {
    0: ("Passive Component",),
    1: ("Basic Sensor", "Basic Actuator", "Basic Communication Device"),
    2: ("Smart Sensor", "Controlled Actuator", "Smart I/O Device", "Embedded Device"),
    3: ("Perception Sensor", "Intelligent Sensor", "Perception Device"),
    4: ("Intelligent Subsystem",),
}

DATA_COMPLEXITIES = (
    "RAW_SCALAR",
    "PHYSICAL_SCALAR",
    "MULTI_VALUE",
    "STRUCTURED_OBJECT",
    "STRUCTURED_OBJECT_LIST",
    "IMAGE_STREAM",
    "POINT_CLOUD",
    "AUDIO_STREAM",
    "SERVICE_DATA",
    "CONTROL_COMMAND",
    "EVENT",
)

CLASSIFICATION_STATUSES = ("UNKNOWN", "PROPOSED", "CONFIRMED", "REVIEW_REQUIRED")


@dataclass(frozen=True)
class DeviceCapabilityProfile:
    device_class: int
    classification_name: str
    device_typing: str
    device_role: str
    intelligence_level: str
    data_complexity: str
    measurement_capabilities: tuple[str, ...] = ()
    actuation_capabilities: tuple[str, ...] = ()
    processing_capabilities: tuple[str, ...] = ()
    diagnostic_capabilities: tuple[str, ...] = ()
    communication_capabilities: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    requires_function_model: bool = False
    requires_status_model: bool = False
    requires_health_model: bool = False
    requires_quality_model: bool = False
    requires_data_object_model: bool = False
    requires_hardware_interface_model: bool = False
    supports_raw_data: bool = True
    supports_streaming: bool = False
    provenance: str = "heuristic"

    @property
    def capability_profile_ref(self) -> str:
        return f"class-{self.device_class}:{self.device_typing.lower().replace(' ', '_').replace('/', '')}"

    @property
    def generator_policy(self) -> dict[str, str | bool]:
        return {
            "auto_function": "YES" if self.requires_function_model else "NO",
            "signals": "YES",
            "status_model": "YES" if self.requires_status_model else "NO",
            "health_model": "YES" if self.requires_health_model else "NO",
            "quality_model": "YES" if self.requires_quality_model else "OPTIONAL",
            "data_object_model": "YES" if self.requires_data_object_model else "NO",
            "stream": self.supports_streaming,
            "hardware_interface": "YES" if self.requires_hardware_interface_model else "OPTIONAL",
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capability_profile_ref"] = self.capability_profile_ref
        payload["generator_policy"] = self.generator_policy
        return payload


class DeviceClassificationRegistry:
    """Resolve class, typing and capabilities from HardwareNode metadata."""

    def resolve_profile(
        self,
        *,
        name: str = "",
        device_type: str = "GenericDevice",
        device_class: int | str | None = None,
        device_typing: str | None = None,
        data_complexity: str | None = None,
    ) -> DeviceCapabilityProfile:
        inferred_class, inferred_typing, role, complexity = self._infer(name, device_type)
        resolved_class = self.resolve_class(device_class, inferred_class)
        resolved_typing = self.resolve_typing(device_typing, resolved_class, inferred_typing)
        resolved_complexity = self.resolve_data_complexity(data_complexity, complexity)
        return self.resolve_default_capabilities(
            device_class=resolved_class,
            device_typing=resolved_typing,
            device_role=role,
            data_complexity=resolved_complexity,
            provenance="user_confirmed" if device_class is not None or device_typing else "heuristic",
        )

    def resolve_class(self, value: int | str | None, fallback: int = 1) -> int:
        if value in (None, ""):
            return fallback
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed in DEVICE_CLASSES else fallback

    def resolve_typing(self, value: str | None, device_class: int, fallback: str | None = None) -> str:
        allowed = DEVICE_TYPINGS_BY_CLASS.get(device_class, DEVICE_TYPINGS_BY_CLASS[1])
        if value and value in allowed:
            return value
        if fallback and fallback in allowed:
            return fallback
        return allowed[0]

    def resolve_data_complexity(self, value: str | None, fallback: str = "SERVICE_DATA") -> str:
        return value if value in DATA_COMPLEXITIES else fallback

    def resolve_default_capabilities(
        self,
        *,
        device_class: int,
        device_typing: str,
        device_role: str,
        data_complexity: str,
        provenance: str = "heuristic",
    ) -> DeviceCapabilityProfile:
        if device_class == 0:
            return DeviceCapabilityProfile(device_class, DEVICE_CLASSES[device_class], device_typing, device_role, "passive", data_complexity, output_types=("raw",), provenance=provenance)
        if device_class == 1:
            return DeviceCapabilityProfile(
                device_class,
                DEVICE_CLASSES[device_class],
                device_typing,
                device_role,
                "basic",
                data_complexity,
                measurement_capabilities=("physical_signal",) if "Sensor" in device_typing else (),
                actuation_capabilities=("command_signal", "state_feedback") if "Actuator" in device_typing else (),
                communication_capabilities=("basic_link",) if "Communication" in device_typing else (),
                output_types=("signal",),
                requires_quality_model="Sensor" in device_typing,
                provenance=provenance,
            )
        if device_class == 2:
            return DeviceCapabilityProfile(
                device_class,
                DEVICE_CLASSES[device_class],
                device_typing,
                device_role,
                "smart",
                data_complexity,
                measurement_capabilities=("physical_signal", "diagnostics") if "Sensor" in device_typing else (),
                actuation_capabilities=("closed_loop_control", "state_feedback") if "Actuator" in device_typing else (),
                processing_capabilities=("local_preprocessing",),
                diagnostic_capabilities=("self_diagnostics", "health_state"),
                output_types=("signal", "status", "health"),
                requires_status_model=True,
                requires_health_model=True,
                requires_quality_model=True,
                requires_hardware_interface_model=True,
                provenance=provenance,
            )
        if device_class == 3:
            return DeviceCapabilityProfile(
                device_class,
                DEVICE_CLASSES[device_class],
                device_typing,
                device_role,
                "perception",
                data_complexity,
                measurement_capabilities=("perception", "environment_model"),
                processing_capabilities=("feature_extraction", "object_detection"),
                diagnostic_capabilities=("self_diagnostics", "health_state"),
                output_types=("stream", "data_object", "status", "quality"),
                requires_function_model=True,
                requires_status_model=True,
                requires_health_model=True,
                requires_quality_model=True,
                requires_data_object_model=True,
                requires_hardware_interface_model=True,
                supports_streaming=data_complexity in {"IMAGE_STREAM", "POINT_CLOUD", "AUDIO_STREAM"},
                provenance=provenance,
            )
        return DeviceCapabilityProfile(
            device_class,
            DEVICE_CLASSES[device_class],
            device_typing,
            device_role,
            "subsystem",
            data_complexity,
            processing_capabilities=("application_logic", "coordination", "routing"),
            diagnostic_capabilities=("self_diagnostics", "health_state"),
            communication_capabilities=("network_endpoint", "gatewaying"),
            output_types=("service_data", "status", "health"),
            requires_function_model=True,
            requires_status_model=True,
            requires_health_model=True,
            requires_quality_model=True,
            requires_data_object_model=True,
            requires_hardware_interface_model=True,
            provenance=provenance,
        )

    def validate_combination(self, device_class: int, device_typing: str, data_complexity: str) -> tuple[bool, str]:
        if device_class not in DEVICE_CLASSES:
            return False, "Unknown device class"
        if device_typing not in DEVICE_TYPINGS_BY_CLASS[device_class]:
            return False, "Typing does not belong to device class"
        if data_complexity not in DATA_COMPLEXITIES:
            return False, "Unknown data complexity"
        return True, "ok"

    def class_options(self) -> list[dict[str, Any]]:
        return [{"value": key, "label": value} for key, value in DEVICE_CLASSES.items()]

    def profile_options(self) -> list[dict[str, Any]]:
        return [
            self.resolve_profile(device_class=device_class, device_typing=typing).to_dict()
            for device_class, typings in DEVICE_TYPINGS_BY_CLASS.items()
            for typing in typings
        ]

    def _infer(self, name: str, device_type: str) -> tuple[int, str, str, str]:
        haystack = f"{name} {device_type}".lower()
        if device_type == "Gateway" or "gateway" in haystack:
            return 4, "Intelligent Subsystem", "gateway", "SERVICE_DATA"
        if device_type in {"ECU", "PLC", "RobotController", "EmbeddedController", "IndustrialPC", "FlightComputer", "BatteryManagementSystem", "EnergyController", "BuildingController"}:
            return 4, "Intelligent Subsystem", "controller", "SERVICE_DATA"
        if any(token in haystack for token in ("camera", "kamera", "vision")):
            return 3, "Perception Sensor", "sensor", "IMAGE_STREAM"
        if "radar" in haystack or "ultrasonic array" in haystack:
            return 3, "Perception Sensor", "sensor", "STRUCTURED_OBJECT_LIST"
        if "lidar" in haystack or "scanner" in haystack:
            return 3, "Perception Device", "sensor", "POINT_CLOUD"
        if "advanced imu" in haystack:
            return 3, "Intelligent Sensor", "sensor", "MULTI_VALUE"
        if device_type == "SensorController" or "sensor" in haystack:
            if any(token in haystack for token in ("smart", "digital", "diagnostic", "imu", "encoder")):
                return 2, "Smart Sensor", "sensor", "MULTI_VALUE"
            return 1, "Basic Sensor", "sensor", "PHYSICAL_SCALAR"
        if device_type == "ActuatorController" or any(token in haystack for token in ("actuator", "aktor", "valve", "pump", "servo", "motor")):
            if any(token in haystack for token in ("servo", "controlled", "smart", "pump", "driver")):
                return 2, "Controlled Actuator", "actuator", "CONTROL_COMMAND"
            return 1, "Basic Actuator", "actuator", "CONTROL_COMMAND"
        if any(token in haystack for token in ("thermistor", "pt100", "potentiometer", "switch", "relay", "lamp")):
            return 0, "Passive Component", "passive", "RAW_SCALAR"
        return 1, "Basic Communication Device", "communication", "SERVICE_DATA"
