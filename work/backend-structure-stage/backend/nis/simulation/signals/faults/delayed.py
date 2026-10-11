from __future__ import annotations

from typing import Any


def delayed(behavior: Any, signal_id: str, time_s: float, delay_s: float, fallback: float) -> float:
    return behavior.delayed(signal_id, time_s, max(0.0, delay_s), fallback)
