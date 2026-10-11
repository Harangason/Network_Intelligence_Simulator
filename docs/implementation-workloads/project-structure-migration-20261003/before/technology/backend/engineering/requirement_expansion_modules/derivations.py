"""Deterministic derivation helpers for the requirement-expansion proposal."""

from __future__ import annotations

from math import ceil
from typing import Any

from .constants import (
    AUTOMOTIVE_ETHERNET_MAX_BITRATE_MBIT_S,
    CAN_FD_MAX_BITRATE_MBIT_S,
    CAN_FD_PAYLOAD_BYTES,
    ETHERNET_MAX_BITRATE_MBIT_S,
)
from .text_utils import extract_int, round_digits, safe_float


def _param(parameters: list[dict[str, Any]], name: str, default: float) -> float:
    return safe_float(next((item.get("value") for item in parameters if item.get("name") == name), default), default)


def _next_can_fd_payload(payload_bytes: int) -> int | None:
    for candidate in CAN_FD_PAYLOAD_BYTES:
        if candidate >= payload_bytes:
            return candidate
    return None


def derive_functions(text: str, sensor_family: str) -> list[dict[str, Any]]:
    if sensor_family == "camera":
        return [
            {
                "name": "EnvironmentPerception",
                "status": "PROPOSED",
                "subfunctions": [
                    "CaptureCameraImages",
                    "SynchronizeCameraData",
                    "CorrectCameraImage",
                    "DetectObjects",
                    "TransformCoordinates",
                    "FuseDetections",
                    "TrackObjects",
                    "MonitorCoverage",
                    "MonitorCameraHealth",
                    "ProvideEnvironmentModel",
                ],
                "inputs": ["CameraFrames"],
                "outputs": ["EnvironmentObjectList"],
            }
        ]
    if sensor_family == "temperature":
        return [
            {
                "name": "TemperatureMonitoring",
                "status": "PROPOSED",
                "subfunctions": ["AcquireTemperature", "ValidateTemperatureQuality", "PublishTemperatureState"],
                "inputs": ["TemperatureSensors"],
                "outputs": ["TemperatureEnvelope"],
            }
        ]
    if sensor_family == "pressure":
        return [
            {
                "name": "PressureControl",
                "status": "PROPOSED",
                "subfunctions": ["ReadPressure", "EstimatePressure", "TriggerSafetyActions", "ReportStatus"],
                "inputs": ["PressureSensors"],
                "outputs": ["PressureState"],
            }
        ]
    if sensor_family == "position":
        return [
            {
                "name": "PositionTracking",
                "status": "PROPOSED",
                "subfunctions": ["AcquirePose", "FusePose", "PublishMotionState"],
                "inputs": ["PositionSource"],
                "outputs": ["PositionState"],
            }
        ]
    if sensor_family in {"lidar", "radar", "ultrasonic"}:
        return [
            {
                "name": f"{sensor_family.title()}Perception",
                "status": "PROPOSED",
                "subfunctions": [
                    f"Acquire{sensor_family.title()}Data",
                    "ValidateSensorQuality",
                    "FilterDetections",
                    "TransformCoordinates",
                    "PublishPerceptionState",
                ],
                "inputs": [f"{sensor_family.title()}Samples"],
                "outputs": [f"{sensor_family.title()}DetectionList"],
            }
        ]
    return [
        {
            "name": "GenericFunctionalization",
            "status": "PROPOSED",
            "subfunctions": ["AcquireInputs", "TransformData", "PublishState"],
            "inputs": ["RawInput"],
            "outputs": ["DomainOutput"],
        }
    ]


def derive_sensors(
    resolved_family: str,
    assumptions: list[dict[str, Any]],
    text: str,
) -> list[dict[str, Any]]:
    requested_count = int(extract_int(text, (r"(\d+)\s*\b(?:kamera|cameras|camera)\b",)) or 0)
    if resolved_family == "camera":
        required_coverage = next((item["proposed_value"] for item in assumptions if item["concept"] == "required_coverage"), 360.0)
        if requested_count <= 0:
            hfov = 110.0
            overlap = 20.0
            effective = max(1.0, hfov - overlap)
            requested_count = int(ceil(float(required_coverage) / effective))
        positions = ["front", "rear", "left", "right", "front_left", "front_right", "rear_left", "rear_right"]
        return [
            {
                "name": "SurroundCameraSet",
                "kind": "Camera",
                "proposed_count": requested_count,
                "proposed_positions": positions[:max(1, requested_count)],
                "assumptions": {
                    "hfov_deg": 110.0,
                    "vFov_deg": 90.0,
                    "frame_rate": next(item["proposed_value"] for item in assumptions if item["concept"] == "frame_rate"),
                },
                "status": "PROPOSED",
            }
        ]
    if resolved_family in {"lidar", "radar", "ultrasonic"}:
        defaults = {
            "lidar": ("LidarSensor", "LidarSensor", ["front_center"], {"range_m": 120.0, "horizontal_fov_deg": 120.0}),
            "radar": ("RadarSensor", "RadarSensor", ["front_center", "rear_center"], {"range_m": 180.0, "horizontal_fov_deg": 80.0}),
            "ultrasonic": ("UltrasonicSensorSet", "UltrasonicSensor", ["front", "rear", "left", "right"], {"range_m": 5.0, "horizontal_fov_deg": 60.0}),
        }
        name, kind, positions, family_assumptions = defaults[resolved_family]
        return [
            {
                "name": name,
                "kind": kind,
                "proposed_count": len(positions),
                "proposed_positions": positions,
                "assumptions": family_assumptions,
                "status": "PROPOSED",
            }
        ]
    if resolved_family == "temperature":
        return [
            {
                "name": "TemperatureProbe",
                "kind": "TemperatureSensor",
                "proposed_count": 1,
                "status": "PROPOSED",
                "assumptions": {"placement": "near_critical_assets"},
            }
        ]
    if resolved_family == "pressure":
        return [
            {
                "name": "PressureTransducer",
                "kind": "PressureSensor",
                "proposed_count": 1,
                "status": "PROPOSED",
                "assumptions": {"placement": "critical_pressure_nodes"},
            }
        ]
    return [
        {
            "name": "GenericSensor",
            "kind": "InputSource",
            "proposed_count": 1,
            "status": "PROPOSED",
            "assumptions": {"placement": "domain_relevant"},
        }
    ]


def derive_coordinate_system(resolved_family: str) -> dict[str, Any] | None:
    if resolved_family not in {"camera", "lidar", "radar", "ultrasonic", "position"}:
        return None
    return {
        "name": "VehicleFrame" if resolved_family != "position" else "WorldFrame",
        "x_axis": "forward",
        "y_axis": "left",
        "z_axis": "up",
        "origin": "VehicleReferencePoint",
        "units": {"position": "m", "rotation_deg": "deg"},
        "status": "PROPOSED",
    }


def derive_parameters(
    text: str,
    resolved_family: str,
    assumptions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    frame_rate = extract_int(text, (r"(\d+)\s*(?:hz|fps|frame rate|bildfrequenz)\b",), default=None) or next(
        (item["proposed_value"] for item in assumptions if item["concept"] == "frame_rate"),
        30,
    )
    params: list[dict[str, Any]] = [
        {"name": "sample_rate", "value": frame_rate, "unit": "Hz", "status": "PROPOSED"},
    ]
    if resolved_family == "camera":
        params.extend([
            {"name": "horizontal_fov", "value": 110.0, "unit": "deg", "status": "KNOWN"},
            {"name": "resolution_x", "value": 1920, "unit": "px", "status": "PROPOSED"},
            {"name": "resolution_y", "value": 1080, "unit": "px", "status": "PROPOSED"},
            {"name": "bit_depth", "value": 24, "unit": "bit", "status": "DEFAULTED"},
            {"name": "overlap_deg", "value": 20.0, "unit": "deg", "status": "PROPOSED"},
        ])
    elif resolved_family in {"lidar", "radar"}:
        params.extend([
            {"name": "horizontal_fov", "value": 120.0 if resolved_family == "lidar" else 80.0, "unit": "deg", "status": "PROPOSED"},
            {"name": "range", "value": 120.0 if resolved_family == "lidar" else 180.0, "unit": "m", "status": "PROPOSED"},
            {"name": "detection_payload", "value": 32, "unit": "byte", "status": "DEFAULTED"},
            {"name": "max_detections", "value": 64, "unit": "count", "status": "DEFAULTED"},
        ])
    else:
        params.append({"name": "sampling_period", "value": 100, "unit": "ms", "status": "PROPOSED"})
    return params


def derive_status_models(resolved_family: str) -> list[dict[str, Any]]:
    if resolved_family == "camera":
        return [
            {
                "name": "CameraOperatingState",
                "states": ["OFF", "INIT", "CALIBRATING", "READY", "ACTIVE", "STANDBY"],
                "status": "PROPOSED",
            },
            {
                "name": "CameraHealthState",
                "states": ["OK", "WARNING", "DEGRADED", "ERROR", "CRITICAL"],
                "status": "PROPOSED",
            },
            {
                "name": "CameraDataQuality",
                "states": ["VALID", "DEGRADED", "BLOCKED", "DIRTY", "OVEREXPOSED", "UNDEREXPOSED", "NOT_AVAILABLE", "STALE"],
                "status": "PROPOSED",
            },
        ]
    if resolved_family in {"lidar", "radar", "ultrasonic"}:
        prefix = resolved_family.title()
        return [
            {
                "name": f"{prefix}OperatingState",
                "states": ["OFF", "INIT", "READY", "ACTIVE", "DEGRADED", "ERROR"],
                "status": "PROPOSED",
            },
            {
                "name": f"{prefix}DataQuality",
                "states": ["VALID", "DEGRADED", "BLOCKED", "NOT_AVAILABLE", "STALE"],
                "status": "PROPOSED",
            },
        ]
    return [
        {
            "name": f"{resolved_family.title()}OperatingState",
            "states": ["OFF", "INITIALIZING", "READY", "ACTIVE", "FAULT", "DEGRADED", "ERROR"],
            "status": "PROPOSED",
        }
    ]


def derive_data_objects(resolved_family: str, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if resolved_family == "camera":
        return [
            {
                "name": "EnvironmentObject",
                "fields": [
                    "object_id",
                    "object_class",
                    "position",
                    "orientation",
                    "velocity",
                    "acceleration",
                    "dimensions",
                    "confidence",
                    "timestamp",
                ],
                "status": "PROPOSED",
            },
            {
                "name": "EnvironmentObjectList",
                "fields": ["timestamp", "reference_frame", "object_count", "objects"],
                "status": "PROPOSED",
            },
        ]
    if resolved_family in {"lidar", "radar", "ultrasonic"}:
        prefix = resolved_family.title()
        return [
            {
                "name": f"{prefix}Detection",
                "fields": ["object_id", "distance", "azimuth", "elevation", "relative_velocity", "confidence", "timestamp"],
                "status": "PROPOSED",
            },
            {
                "name": f"{prefix}DetectionList",
                "fields": ["timestamp", "reference_frame", "detection_count", "detections"],
                "status": "PROPOSED",
            },
        ]
    return [{"name": functions[0]["outputs"][0], "status": "PROPOSED", "fields": ["status", "confidence", "timestamp"]}]


def derive_signals(resolved_family: str, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs = [item for function in functions for item in function.get("outputs", [])]
    signals = [
        {
            "name": str(outputs[0] if outputs else "DomainState"),
            "kind": "State",
            "proposed_bus": "CAN_FD",
            "producer_function": (functions[0]["name"] if functions else "RootFunction"),
            "status": "PROPOSED",
        }
    ]
    if resolved_family == "camera":
        signals.extend([
            {"name": "CameraOperatingState", "kind": "Status", "status": "PROPOSED"},
            {"name": "CameraHealthState", "kind": "Status", "status": "PROPOSED"},
            {"name": "CameraDataQuality", "kind": "Status", "status": "PROPOSED"},
            {"name": "CameraFrameCounter", "kind": "Counter", "status": "PROPOSED"},
        ])
    elif resolved_family in {"lidar", "radar", "ultrasonic"}:
        prefix = resolved_family.title()
        signals.extend([
            {"name": f"{prefix}OperatingState", "kind": "Status", "status": "PROPOSED"},
            {"name": f"{prefix}DataQuality", "kind": "Status", "status": "PROPOSED"},
            {"name": f"{prefix}DetectionCounter", "kind": "Counter", "status": "PROPOSED"},
        ])
    return signals


def derive_hardware(resolved_family: str, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = {
        "camera": ["VisionController", "ADASController"],
        "temperature": ["ThermalController"],
        "pressure": ["PressureController"],
        "position": ["LocalizationController", "PerceptionController"],
        "lidar": ["PerceptionController", "SensorFusionController"],
        "radar": ["PerceptionController", "ADASController"],
        "ultrasonic": ["BodyController", "ParkingController"],
    }
    return [
        {
            "name": mapping.get(resolved_family, [f"{resolved_family.title()}Controller"])[0],
            "functions": [item["name"] for item in functions],
            "status": "PROPOSED",
        }
    ]


def derive_capacity(resolved_family: str, sensors: list[dict[str, Any]], parameters: list[dict[str, Any]]) -> dict[str, Any]:
    sensor_count = max(1, int(sensors[0].get("proposed_count", 1))) if sensors else 1
    frame_rate = _param(parameters, "sample_rate", 30)
    if resolved_family != "camera":
        detection_payload = _param(parameters, "detection_payload", 16)
        max_detections = _param(parameters, "max_detections", 16)
        raw_mbit_per_second = detection_payload * 8.0 * max_detections * frame_rate * sensor_count / 1_000_000.0
        raw_mbit_per_second = max(raw_mbit_per_second, 0.5 if resolved_family == "generic" else raw_mbit_per_second)
        utilization = raw_mbit_per_second / CAN_FD_MAX_BITRATE_MBIT_S
        return {
            "raw_mbit_s": round_digits(raw_mbit_per_second),
            "effective_mbit_s": round_digits(raw_mbit_per_second),
            "suggested_technology": "CAN_FD" if utilization < 0.5 else "AUTOMOTIVE_ETHERNET",
            "capacity_limit_mbit_s": CAN_FD_MAX_BITRATE_MBIT_S,
            "estimated_utilization": round_digits(utilization),
            "cycle_time_ms": round_digits(1000.0 / max(frame_rate, 1.0)),
            "latency_budget_ms": 50,
            "status": "PROPOSED",
        }
    resolution_x = _param(parameters, "resolution_x", 1920)
    resolution_y = _param(parameters, "resolution_y", 1080)
    bit_depth = _param(parameters, "bit_depth", 24)
    camera_count = max(1, int(sensors[0].get("proposed_count", 1)))
    raw_bits_per_second = float(resolution_x) * float(resolution_y) * float(bit_depth) * float(frame_rate) * camera_count
    raw_mbit_per_second = raw_bits_per_second / 1_000_000.0
    if raw_mbit_per_second > 200.0:
        network = "ETHERNET"
    elif raw_mbit_per_second > 30.0:
        network = "AUTOMOTIVE_ETHERNET"
    else:
        network = "CAN_FD"
    return {
        "raw_mbit_s": round_digits(raw_mbit_per_second),
        "suggested_technology": network,
        "estimated_compression": 0.6,
        "effective_mbit_s": round_digits(raw_mbit_per_second * 0.6),
        "capacity_limit_mbit_s": ETHERNET_MAX_BITRATE_MBIT_S if network == "ETHERNET" else AUTOMOTIVE_ETHERNET_MAX_BITRATE_MBIT_S if network == "AUTOMOTIVE_ETHERNET" else CAN_FD_MAX_BITRATE_MBIT_S,
        "estimated_utilization": round_digits((raw_mbit_per_second * 0.6) / (ETHERNET_MAX_BITRATE_MBIT_S if network == "ETHERNET" else AUTOMOTIVE_ETHERNET_MAX_BITRATE_MBIT_S if network == "AUTOMOTIVE_ETHERNET" else CAN_FD_MAX_BITRATE_MBIT_S)),
        "cycle_time_ms": round_digits(1000.0 / max(float(frame_rate), 1.0)),
        "latency_budget_ms": 20,
        "status": "PROPOSED",
    }


def derive_communications(resolved_family: str, capacity: dict[str, Any], sensors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if resolved_family == "camera":
        return [
            {
                "sender": sensors[0]["name"],
                "message": "RawCameraFrames",
                "transport": "ETHERNET" if "ETHERNET" in str(capacity.get("suggested_technology", "")) else "CAN_FD",
                "priority": "high",
                "latency_target_ms": 20,
                "status": "PROPOSED",
            },
            {
                "sender": sensors[0]["name"],
                "message": "CameraStatus",
                "transport": "CAN_FD",
                "priority": "medium",
                "latency_target_ms": 100,
                "status": "PROPOSED",
            },
        ]
    return [
        {
            "sender": sensors[0]["name"],
            "message": "DomainStatus",
            "transport": "CAN_FD",
            "priority": "medium",
            "latency_target_ms": 50,
            "status": "PROPOSED",
        }
    ]


def derive_messages(capacity: dict[str, Any], resolved_family: str) -> list[dict[str, Any]]:
    status_payload = _next_can_fd_payload(8) or 8
    suggestions = [
        {
            "name": "DomainStatusMessage",
            "transport": "CAN_FD",
            "payload_bytes": status_payload,
            "packed_payload_bytes": status_payload,
            "payload_policy": "MINIMUM_VALID_SIZE",
            "cycle_time_ms": 100,
            "status": "PROPOSED",
        }
    ]
    if resolved_family == "camera":
        suggestions.append({
            "name": "RawCameraStream",
            "transport": capacity.get("suggested_technology"),
            "payload_bytes": None,
            "packed_payload_bytes": None,
            "payload_policy": "MANUAL",
            "cycle_time_ms": capacity.get("cycle_time_ms"),
            "status": "PROPOSED",
            "requires_review": True,
        })
    elif resolved_family in {"lidar", "radar", "ultrasonic"}:
        payload = _next_can_fd_payload(32) or 64
        suggestions.append({
            "name": f"{resolved_family.title()}DetectionMessage",
            "transport": capacity.get("suggested_technology"),
            "payload_bytes": payload,
            "packed_payload_bytes": payload,
            "payload_policy": "CAN_FD_ALIGNED",
            "cycle_time_ms": capacity.get("cycle_time_ms"),
            "status": "PROPOSED",
        })
    return suggestions


def derive_routing(_text: str, hardware: list[dict[str, Any]], communications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    media = communications[0].get("transport") if communications else "CAN_FD"
    source = communications[0].get("sender") if communications else "SourceNode"
    target = hardware[0].get("name") if hardware else "Controller"
    return [
        {
            "from": source,
            "to": target,
            "via": "GatewayNode" if str(media).upper() in {"CAN", "CAN_FD"} else "EthernetSwitch",
            "media": media,
            "routing_policy": "time_sensitive" if any("Camera" in str(item.get("message", "")) or "Stream" in str(item.get("message", "")) for item in communications) else "normal",
            "status": "PROPOSED",
        }
    ]
