from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalSpec:
    name: str
    factor: float
    offset: float
    minimum: int
    maximum: int
    unit: str
    kind: str = "normal"


TRACE_REALISM_MODEL = "industry_physical_baseline_v1"


def trace_quality_summary() -> dict[str, object]:
    return {
        "model": TRACE_REALISM_MODEL,
        "intent": "industry-oriented physical baseline for simulated CAN/Ethernet traces",
        "signal_semantics": "named engineering signals with units, scaling, offsets, and bounded raw ranges",
        "state_sources": [
            "ego speed and acceleration",
            "steering angle and yaw rate",
            "object distance and relative speed",
            "brake pressure and controller status",
            "temperature, voltage, current, and health states",
        ],
        "determinism": "seeded scheduling plus deterministic physical state functions",
        "external_signal_policy": "external signal definitions are preserved unchanged and override built-in signal catalogs",
        "limits": [
            "synthetic baseline, not a certified vehicle dynamics model",
            "signed engineering values are encoded through unsigned raw values with DBC offsets",
        ],
    }


def external_signal_records(raw_signals: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_signals, list):
        return []
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_signals):
        if not isinstance(raw, dict):
            continue
        name = raw.get("name") or raw.get("signal") or raw.get("short_name")
        if not name:
            raise ValueError(f"external signal at index {index} needs a name")
        start_bit = raw.get("start_bit", raw.get("startBit", raw.get("bit_start", raw.get("bitOffset"))))
        length = raw.get("length", raw.get("bit_length", raw.get("bitLength", raw.get("size"))))
        if start_bit is None or length is None:
            raise ValueError(f"external signal '{name}' needs start_bit and length")
        records.append(
            {
                "name": str(name),
                "start_bit": int(start_bit),
                "length": int(length),
                "factor": float(raw.get("factor", raw.get("scale", 1.0))),
                "offset": float(raw.get("offset", 0.0)),
                "minimum": int(raw.get("minimum", raw.get("min", 0))),
                "maximum": int(raw.get("maximum", raw.get("max", (1 << int(length)) - 1))),
                "unit": str(raw.get("unit", raw.get("units", ""))),
                "kind": str(raw.get("kind", raw.get("role", "normal"))),
            }
        )
    return records


def contains_external_signal_records(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(item, dict) for item in value)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _fit_to_length(spec: SignalSpec, bit_length: int) -> SignalSpec:
    raw_max = (1 << bit_length) - 1
    if spec.maximum <= raw_max:
        return spec
    upper = spec.offset + spec.factor * spec.maximum
    lower = spec.offset + spec.factor * spec.minimum
    factor = (upper - lower) / raw_max if raw_max else spec.factor
    return SignalSpec(spec.name, factor, lower, 0, raw_max, spec.unit, spec.kind)


def _base_signal_catalog(text: str) -> list[SignalSpec]:
    perception = [
        SignalSpec("ObjectDistanceM", 0.1, 0.0, 0, 2500, "m"),
        SignalSpec("ObjectRelSpeedKph", 0.1, -200.0, 0, 4095, "km/h"),
        SignalSpec("ObjectAzimuthDeg", 0.1, -120.0, 0, 2400, "deg"),
        SignalSpec("ObjectCount", 1.0, 0.0, 0, 64, "obj"),
        SignalSpec("SensorConfidencePct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("LaneCurvatureInvKm", 0.01, -20.0, 0, 4000, "1/km"),
        SignalSpec("EgoSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("YawRateDps", 0.1, -200.0, 0, 4095, "deg/s"),
        SignalSpec("SensorTemperatureC", 0.1, -40.0, 0, 2000, "C"),
        SignalSpec("SupplyVoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("QualityCounter", 1.0, 0.0, 0, 4095, ""),
    ]
    braking = [
        SignalSpec("WheelSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("BrakePressureBar", 0.1, 0.0, 0, 2500, "bar"),
        SignalSpec("BrakePedalPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("EscActive", 1.0, 0.0, 0, 1, ""),
        SignalSpec("AbsActive", 1.0, 0.0, 0, 1, ""),
        SignalSpec("LongAccelMps2", 0.01, -20.0, 0, 4000, "m/s2"),
        SignalSpec("YawRateDps", 0.1, -200.0, 0, 4095, "deg/s"),
        SignalSpec("BrakeTemperatureC", 0.1, -40.0, 0, 2200, "C"),
        SignalSpec("SupplyVoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("EgoSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("Standstill", 1.0, 0.0, 0, 1, ""),
    ]
    steering = [
        SignalSpec("SteeringAngleDeg", 0.1, -200.0, 0, 4095, "deg"),
        SignalSpec("SteeringTorqueNm", 0.1, -80.0, 0, 1600, "Nm"),
        SignalSpec("YawRateDps", 0.1, -200.0, 0, 4095, "deg/s"),
        SignalSpec("LateralAccelMps2", 0.01, -20.0, 0, 4000, "m/s2"),
        SignalSpec("EgoSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("LaneOffsetM", 0.01, -10.0, 0, 2000, "m"),
        SignalSpec("AssistTorqueNm", 0.1, -80.0, 0, 1600, "Nm"),
        SignalSpec("SupplyVoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("MotorCurrentA", 0.1, -200.0, 0, 4000, "A"),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("CommandValid", 1.0, 0.0, 0, 1, ""),
        SignalSpec("DriverOverridePct", 1.0, 0.0, 0, 100, "%"),
    ]
    powertrain = [
        SignalSpec("EngineSpeedRpm", 1.0, 0.0, 0, 8000, "rpm"),
        SignalSpec("ActualTorqueNm", 0.1, -500.0, 0, 10000, "Nm"),
        SignalSpec("PedalPositionPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("GearActual", 1.0, 0.0, 0, 10, ""),
        SignalSpec("EgoSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("CoolantTemperatureC", 0.1, -40.0, 0, 2000, "C"),
        SignalSpec("OilPressureBar", 0.01, 0.0, 0, 1200, "bar"),
        SignalSpec("BatterySocPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("HvVoltageV", 0.1, 0.0, 0, 9000, "V"),
        SignalSpec("InverterCurrentA", 0.1, -600.0, 0, 12000, "A"),
        SignalSpec("ThermalLimitPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
    ]
    body = [
        SignalSpec("DoorStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("LockState", 1.0, 0.0, 0, 15, ""),
        SignalSpec("IgnitionState", 1.0, 0.0, 0, 7, ""),
        SignalSpec("InteriorTemperatureC", 0.1, -40.0, 0, 1200, "C"),
        SignalSpec("AmbientTemperatureC", 0.1, -40.0, 0, 1200, "C"),
        SignalSpec("FanSpeedPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("SeatPositionMm", 1.0, 0.0, 0, 300, "mm"),
        SignalSpec("LightCommandPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("SupplyVoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("DiagnosticStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("NetworkManagementState", 1.0, 0.0, 0, 15, ""),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
    ]
    if any(token in text for token in ["lidar", "radar", "camera", "object", "lane", "adas", "imu"]):
        return perception
    if any(token in text for token in ["brake", "esc", "abs", "wheel"]):
        return braking
    if any(token in text for token in ["steer", "trajectory", "lane_change"]):
        return steering
    if any(token in text for token in ["powertrain", "engine", "torque", "gear", "battery", "inverter", "motor"]):
        return powertrain
    if any(token in text for token in ["body", "door", "lock", "kessy", "hvac", "seat", "light", "infotainment"]):
        return body
    return [
        SignalSpec("EgoSpeedKph", 0.1, 0.0, 0, 2500, "km/h"),
        SignalSpec("LongAccelMps2", 0.01, -20.0, 0, 4000, "m/s2"),
        SignalSpec("YawRateDps", 0.1, -200.0, 0, 4095, "deg/s"),
        SignalSpec("SignalQualityPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("SupplyVoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("EcuTemperatureC", 0.1, -40.0, 0, 2000, "C"),
        SignalSpec("CommandValid", 1.0, 0.0, 0, 1, ""),
        SignalSpec("HealthStatus", 1.0, 0.0, 0, 15, ""),
        SignalSpec("LoadPct", 1.0, 0.0, 0, 100, "%"),
        SignalSpec("CurrentA", 0.1, -200.0, 0, 4000, "A"),
        SignalSpec("VoltageV", 0.01, 0.0, 0, 6000, "V"),
        SignalSpec("DiagnosticStatus", 1.0, 0.0, 0, 15, ""),
    ]


def signal_specs_for_message(
    sender: str,
    receiver: str,
    message_name: str,
    signal_count: int,
    bit_length: int,
) -> list[SignalSpec]:
    text = f"{sender} {receiver} {message_name}".lower()
    catalog = _base_signal_catalog(text)
    specs = [catalog[index % len(catalog)] for index in range(signal_count)]
    return [_fit_to_length(spec, bit_length) for spec in specs]


def _scenario_state(t_s: float) -> dict[str, float]:
    phase = t_s % 12.0
    if phase < 4.0:
        speed = 35.0 + phase * 10.0
        accel = 2.78
    elif phase < 7.0:
        speed = 75.0 + 3.0 * math.sin((phase - 4.0) * math.pi / 3.0)
        accel = 0.4 * math.cos((phase - 4.0) * math.pi / 3.0)
    elif phase < 9.0:
        speed = 75.0 - (phase - 7.0) * 22.0
        accel = -6.1
    else:
        speed = 31.0 + (phase - 9.0) * 2.0
        accel = 0.55
    steering = 9.0 * math.sin(t_s * 0.7) + 2.5 * math.sin(t_s * 1.9)
    yaw_rate = steering * max(speed, 1.0) / 180.0
    object_distance = clamp(96.0 - phase * 7.5 + 8.0 * math.sin(t_s * 0.6), 6.0, 160.0)
    brake_pressure = clamp(-accel * 22.0 + (28.0 if phase >= 7.0 and phase < 9.0 else 0.0), 0.0, 180.0)
    return {
        "speed": speed,
        "accel": accel,
        "steering": steering,
        "yaw_rate": yaw_rate,
        "object_distance": object_distance,
        "brake_pressure": brake_pressure,
        "confidence": clamp(96.0 - abs(steering) * 0.5 - max(0.0, 30.0 - object_distance) * 0.3, 45.0, 99.0),
        "temperature": 72.0 + 5.0 * math.sin(t_s / 18.0),
        "ambient": 21.0 + 3.0 * math.sin(t_s / 45.0),
        "voltage": 13.6 + 0.15 * math.sin(t_s * 0.8),
    }


def _noise(frame_id: int, signal_index: int, t_s: float, amplitude: float) -> float:
    return amplitude * math.sin(t_s * 3.1 + frame_id * 0.017 + signal_index * 1.37)


def _engineering_value(name: str, t_s: float, frame_id: int, signal_index: int) -> float:
    state = _scenario_state(t_s)
    lname = name.lower()
    if "speed" in lname and "rel" not in lname and "engine" not in lname:
        return state["speed"] + _noise(frame_id, signal_index, t_s, 0.7)
    if "engine" in lname and "rpm" in lname:
        return 800.0 + state["speed"] * 38.0 + _noise(frame_id, signal_index, t_s, 45.0)
    if "torque" in lname:
        return 80.0 + state["accel"] * 42.0 + _noise(frame_id, signal_index, t_s, 8.0)
    if "pedal" in lname:
        return clamp(22.0 + max(state["accel"], 0.0) * 18.0, 0.0, 100.0)
    if "gear" in lname:
        return clamp(round(1.0 + state["speed"] / 28.0), 1.0, 8.0)
    if "distance" in lname or "range" in lname:
        return state["object_distance"] + _noise(frame_id, signal_index, t_s, 0.4)
    if "relspeed" in lname or "rel_speed" in lname:
        return -8.0 - 3.0 * math.sin(t_s * 0.4) + _noise(frame_id, signal_index, t_s, 0.3)
    if "azimuth" in lname:
        return 4.0 * math.sin(t_s * 0.45) + _noise(frame_id, signal_index, t_s, 0.2)
    if "objectcount" in lname or "object_count" in lname:
        return 2.0 + int((t_s % 8.0) > 3.0) + int(state["object_distance"] < 45.0)
    if "confidence" in lname or "quality" in lname:
        return state["confidence"] + _noise(frame_id, signal_index, t_s, 0.5)
    if "steeringangle" in lname or "laneoffset" in lname:
        return state["steering"] + _noise(frame_id, signal_index, t_s, 0.15)
    if "yaw" in lname:
        return state["yaw_rate"] + _noise(frame_id, signal_index, t_s, 0.08)
    if "lateral" in lname:
        return state["yaw_rate"] * state["speed"] / 80.0
    if "longaccel" in lname:
        return state["accel"] + _noise(frame_id, signal_index, t_s, 0.04)
    if "brakepressure" in lname:
        return state["brake_pressure"] + _noise(frame_id, signal_index, t_s, 0.7)
    if "brakepedal" in lname:
        return clamp(state["brake_pressure"] / 1.8, 0.0, 100.0)
    if "active" in lname or "valid" in lname or "standstill" in lname:
        return 1.0 if state["brake_pressure"] > 60.0 or state["speed"] < 2.0 else 0.0
    if "temperature" in lname:
        return (state["ambient"] if "ambient" in lname or "interior" in lname else state["temperature"]) + _noise(frame_id, signal_index, t_s, 0.2)
    if "voltage" in lname:
        return state["voltage"] + _noise(frame_id, signal_index, t_s, 0.02)
    if "current" in lname:
        return 18.0 + abs(state["accel"]) * 12.0 + _noise(frame_id, signal_index, t_s, 1.2)
    if "soc" in lname:
        return 74.0 - (t_s / 3600.0) * 4.0
    if "pressure" in lname:
        return 2.7 + 0.3 * math.sin(t_s * 0.5)
    if "status" in lname or "state" in lname:
        return 1.0 if state["confidence"] > 60.0 else 2.0
    if "counter" in lname:
        return (int(t_s * 10.0) + signal_index) % 4096
    return 50.0 + 20.0 * math.sin(t_s * 0.4 + signal_index)


def physical_raw_value(
    *,
    signal_name: str,
    factor: float,
    offset: float,
    minimum: int,
    maximum: int,
    timestamp_s: float,
    frame_id: int,
    signal_index: int,
) -> int:
    engineering = _engineering_value(signal_name, timestamp_s, frame_id, signal_index)
    raw = round((engineering - offset) / factor) if factor else round(engineering)
    return int(clamp(raw, minimum, maximum))
