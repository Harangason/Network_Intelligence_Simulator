from __future__ import annotations

from typing import Any

from .gaussian import gaussian_noise


def sensor_noise(random_service: Any, signal_id: str, index: int, sigma: float) -> float:
    return gaussian_noise(random_service, sigma, signal_id, "sensor_noise", index)
