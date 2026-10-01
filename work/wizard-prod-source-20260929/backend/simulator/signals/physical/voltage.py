from __future__ import annotations

import math
from typing import Any

from .common import clamp, number


def voltage(signal: Any, time_s: float, context: Any, _state: Any) -> float:
    nominal = number(getattr(context, "environment", {}).get("supply_voltage"), number(signal.parameters.get("nominal_voltage"), 13.6))
    return clamp(nominal + 0.08 * math.sin(time_s * 0.7), signal.minimum, signal.maximum)
