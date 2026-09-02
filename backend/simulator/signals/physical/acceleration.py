from __future__ import annotations

from typing import Any

from .common import clamp, number


def acceleration(signal: Any, _time_s: float, context: Any, _state: Any) -> float:
    target = number(getattr(context, "commands", {}).get(signal.id), number(signal.parameters.get("target_acceleration"), 0.0))
    return clamp(target, signal.minimum, signal.maximum)
