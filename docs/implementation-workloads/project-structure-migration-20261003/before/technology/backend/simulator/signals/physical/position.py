from __future__ import annotations

from typing import Any

import math

from .common import clamp, number, previous_value, time_delta


def position(signal: Any, _time_s: float, context: Any, state: Any) -> float:
    midpoint = (signal.minimum + signal.maximum) / 2.0
    span = signal.maximum - signal.minimum
    vehicle = getattr(context, "system_state", {})
    name = str(signal.name).lower()
    scenario_target = midpoint
    if any(token in name for token in ("damper", "suspension", "federweg", "daempfer", "dämpfer")):
        road = number(vehicle.get("road_input"), 0.0)
        steering = number(vehicle.get("steering_angle_deg"), 0.0)
        side = -1.0 if any(token in name for token in ("left", "links")) else 1.0
        scenario_target = midpoint + span * (road * 0.16 + side * steering / 180.0)
    elif any(token in name for token in ("throttle", "accelerator", "fahrpedal")):
        scenario_target = signal.minimum + span * number(vehicle.get("throttle_percent"), 0.0) / 100.0
    elif any(token in name for token in ("steering", "lenkwinkel")):
        steering = number(vehicle.get("steering_angle_deg"), 0.0)
        scenario_target = clamp(steering, signal.minimum, signal.maximum)
    target = number(getattr(context, "commands", {}).get(signal.id), number(signal.parameters.get("target_position"), scenario_target))
    previous = previous_value(signal, state, signal.minimum)
    dt = time_delta(signal, getattr(context, "current_time", 0.0), state)
    velocity = number(signal.parameters.get("max_velocity"), span * (2.4 if "damper" in name or "suspension" in name else 0.8))
    return clamp(previous + clamp(target - previous, -velocity * dt, velocity * dt), signal.minimum, signal.maximum)
