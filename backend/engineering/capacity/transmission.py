"""Explicit release profiles shared by assessment and executable scenarios.

Event/request intervals bound offered traffic; they are not measured average
rates. Missing triggers must never silently turn into cyclic transmissions.
"""
from math import isfinite


def positive(value):
    try:
        value = float(value)
        return value if isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def profile(contract, legacy_period):
    mode = str(contract.get("mode") or "CYCLIC").upper()
    errors = []
    period = positive(contract.get("period_ms")) or positive(legacy_period)
    minimum = positive(contract.get("minimum_interval_ms"))
    if mode not in {"CYCLIC", "EVENT", "ON_REQUEST", "MIXED"}:
        errors.append("Unbekannter Übertragungsmodus.")
    if mode != "CYCLIC":
        if minimum is None:
            errors.append("Ein begrenzter Mindestabstand für Ereignisse/Anfragen fehlt.")
        if mode in {"EVENT", "MIXED"} and contract.get("trigger") not in {"on_change", "explicit"}:
            errors.append("Ereignisauslöser (on_change oder explicit) fehlt.")
        if mode == "ON_REQUEST" and contract.get("request_source") != "external_application":
            errors.append("Bus-Anfrage und Antwort müssen als zusammengehöriger Verkehr modelliert werden; Anfragequelle ist noch offen.")
        period = minimum
    if not period:
        errors.append("Positiver Sendeabstand fehlt.")
    if mode == "MIXED" and not positive(contract.get("period_ms")):
        errors.append("Heartbeat-Periode für gemischten Betrieb fehlt.")
    if mode == "MIXED" and positive(contract.get("period_ms")) and minimum and float(contract["period_ms"]) < minimum:
        errors.append("Heartbeat unterschreitet den Mindest-Sendeabstand.")
    for key in ("release_times_ms", "request_times_ms"):
        if key not in contract:
            continue
        values = contract[key]
        if not isinstance(values, list) or any(not isinstance(t, (int, float)) or not isfinite(t) or t < 0 for t in values):
            errors.append(f"{key}: nichtnegative endliche Zeitpunkte erforderlich.")
        elif minimum and any(b - a < minimum - 1e-8 for a, b in zip(sorted(set(values)), sorted(set(values))[1:])):
            errors.append(f"{key}: Mindest-Sendeabstand verletzt.")
    return {"mode": mode, "period_ms": period, "errors": errors,
            "load_basis": "PERIODIC_DEMAND" if mode == "CYCLIC" else "BOUNDED_EVENT_DEMAND"}


def release_grid(contract, legacy_period, duration_ms, phase_ms=0, limit=100000):
    """Candidate sampling points; caller suppresses unchanged EVENT payloads."""
    spec = profile(contract, legacy_period)
    if spec["errors"]:
        raise ValueError(" ".join(spec["errors"]))
    mode = spec["mode"]
    key = "request_times_ms" if mode == "ON_REQUEST" else "release_times_ms"
    if mode == "ON_REQUEST" or (mode == "EVENT" and contract.get("trigger") == "explicit"):
        # No scenario requests/events means no response, never a fallback cycle.
        return [float(t) for t in sorted(set(contract.get(key) or [])) if t <= duration_ms][:limit]
    period = spec["period_ms"]
    if mode == "MIXED" and contract.get("trigger") == "explicit":
        heartbeat = float(contract["period_ms"])
        times = set(contract.get("release_times_ms") or []) | {round(phase_ms + i * heartbeat, 9)
            for i in range(min(limit, max(0, int((duration_ms - phase_ms) / heartbeat) + 1)))}
        result = []
        for time in sorted(times):
            time = max(float(time), result[-1] + period if result else 0)
            if time <= duration_ms:
                result.append(time)
        return result[:limit]
    count = min(limit, max(0, int((duration_ms - phase_ms) / period) + 1))
    return [round(phase_ms + index * period, 9) for index in range(count)]
