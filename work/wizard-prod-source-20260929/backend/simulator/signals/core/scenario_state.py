from __future__ import annotations

import math
from typing import Any


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def vehicle_state(time_s: float, scenario: dict[str, Any] | None = None) -> dict[str, float | str]:
    """Return one coherent deterministic vehicle state for every signal model.

    The normalized drive cycle deliberately fits short interactive simulations as
    well as longer runs. Signals therefore react to the same acceleration,
    cruise, manoeuvre and deceleration phases instead of producing unrelated
    synthetic curves.
    """

    settings = scenario or {}
    duration = max(0.1, float(settings.get("duration_s") or 2.0))
    phase = max(0.0, min(1.0, time_s / duration))
    mode = str(settings.get("mode") or "NORMAL").upper()
    stress = 1.25 if mode == "STRESS" else 1.0

    if phase < 0.05:
        operating = "INIT"
    elif phase < 0.12:
        operating = "READY"
    elif phase < 0.2:
        operating = "STARTING"
    elif phase < 0.9:
        operating = "RUNNING"
    elif phase < 0.98:
        operating = "STOPPING"
    else:
        operating = "STANDBY"

    if phase < 0.2:
        speed = 0.0
    elif phase < 0.42:
        speed = 92.0 * _smoothstep((phase - 0.2) / 0.22)
    elif phase < 0.72:
        speed = 92.0 + 8.0 * math.sin((phase - 0.42) / 0.30 * math.pi * 2.0)
    elif phase < 0.9:
        speed = 92.0 * (1.0 - _smoothstep((phase - 0.72) / 0.18))
    else:
        speed = 0.0
    speed = max(0.0, speed * stress)

    throttle = 0.0 if speed <= 0.1 else 34.0 + 18.0 * math.sin(time_s * 2.3) + max(0.0, 92.0 - speed) * 0.18
    throttle = max(0.0, min(100.0, throttle))
    engine_rpm = 0.0 if operating in {"INIT", "READY", "STANDBY"} else 780.0 + speed * 24.0 + throttle * 8.0
    acceleration = 0.0
    if 0.2 <= phase < 0.42:
        acceleration = 2.2 * math.sin((phase - 0.2) / 0.22 * math.pi)
    elif 0.72 <= phase < 0.9:
        acceleration = -2.8 * math.sin((phase - 0.72) / 0.18 * math.pi)
    steering = (5.5 * math.sin(time_s * 1.45) + 1.6 * math.sin(time_s * 4.2)) * min(1.0, speed / 25.0)
    road = (0.62 * math.sin(time_s * 13.0) + 0.28 * math.sin(time_s * 31.0)) * min(1.0, speed / 35.0)
    load = max(0.0, min(1.4, throttle / 100.0 + max(0.0, acceleration) * 0.16))
    braking = max(0.0, -acceleration / 2.8)
    return {
        "operating_state": operating,
        "vehicle_speed_kph": speed,
        "acceleration_mps2": acceleration,
        "throttle_percent": throttle,
        "engine_rpm": engine_rpm,
        "steering_angle_deg": steering,
        "road_input": road,
        "load_factor": load,
        "brake_factor": braking,
    }
