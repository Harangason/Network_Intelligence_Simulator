from __future__ import annotations


HEALTH_CODES = {"OK": 0, "WARNING": 1, "DEGRADED": 2, "ERROR": 3, "CRITICAL": 4}


def health_from_context(context: dict[str, object] | None = None) -> str:
    values = (context or {}).get("signal_values")
    signal_values = values if isinstance(values, dict) else {}
    temperature = max((float(value) for key, value in signal_values.items() if "temp" in str(key).lower()), default=25.0)
    if temperature > 130.0:
        return "CRITICAL"
    if temperature > 110.0:
        return "WARNING"
    return "OK"
