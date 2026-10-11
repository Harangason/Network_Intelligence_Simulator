from __future__ import annotations

from typing import Any


def gaussian_noise(random_service: Any, sigma: float, *seed_parts: object) -> float:
    return random_service.gaussian(0.0, sigma, *seed_parts)
