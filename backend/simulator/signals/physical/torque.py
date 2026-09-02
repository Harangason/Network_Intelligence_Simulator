from __future__ import annotations

import math
from typing import Any

from .common import clamp, number


def torque(signal: Any, time_s: float, context: Any, _state: Any) -> float:
    rpm = max((float(value) for key, value in getattr(context, "signal_values", {}).items() if "rpm" in str(key).lower()), default=0.0)
    if rpm <= 1.0:
        return 0.0
    base = number(signal.parameters.get("base_torque"), 75.0)
    load = 1.0 + 0.25 * math.sin(time_s / 6.0)
    return clamp(base * load, signal.minimum, signal.maximum)
