from __future__ import annotations


def stuck(cache: dict[str, float], signal_id: str, baseline: float) -> float:
    return cache.setdefault(signal_id, baseline)
