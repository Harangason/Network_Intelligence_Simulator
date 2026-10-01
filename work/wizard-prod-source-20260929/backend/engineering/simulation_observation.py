"""Plan an observation window; measured conformance remains the evaluator's job."""
from __future__ import annotations

from copy import deepcopy
from math import floor, isfinite
import re

from .models import EngineeringValidationError

END_MARGIN_MS = 1.0
AUTO_MODES = {"AUTO_REQUIREMENTS", "AUTO_OBSERVATION", "EXPLICIT_REQUEST"}


def _number(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def mark_user_duration(parameters: dict) -> dict:
    """The public parameter-write boundary owns this provenance, never clients."""
    result = deepcopy(parameters)
    provenance = dict(result.get("parameter_provenance") or {})
    for key in ("duration_s", "duration"):
        if key in result:
            provenance[key] = {"source": "USER_PARAMETER", "value": result[key]}
    if provenance:
        result["parameter_provenance"] = provenance
    return result


def wizard_observation_request(prompt: str) -> dict:
    """Honor an explicit duration without mistaking a function deadline for it."""
    number_unit = r"(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*(?P<unit>millisekunden|milliseconds|ms|sekunden|seconds|s|minuten|minutes|min)\b"
    patterns = [
        r"\b(?:simulationsdauer|simulation\s+duration|beobachtungsdauer)\s*[:=]?\s*" + number_unit,
        r"\b(?:simulier\w*|simulat\w*)[^.\r\n]{0,70}?\b(?:für|fuer|for|dauer|duration)\s*[:=]?\s*" + number_unit,
        r"\b(?:für|fuer|for)\s*" + number_unit + r"\s+(?:simulier\w*|simulat\w*)\b",
    ]
    values = set()
    for pattern in patterns:
        for match in re.finditer(pattern, prompt, re.I):
            unit = match["unit"].casefold()
            multiplier = 0.001 if unit in {"ms", "millisekunden", "milliseconds"} else 60 if unit in {"min", "minuten", "minutes"} else 1
            values.add(float(match["value"].replace(",", ".")) * multiplier)
    if len(values) > 1:
        raise EngineeringValidationError("Mehrere unterschiedliche Simulationsdauern sind angegeben; Vorgabe präzisieren.")
    request = {"duration_mode": "AUTO_OBSERVATION", "observation_window": {"mode": "AUTO_REQUIREMENTS"}}
    if values:
        value = values.pop()
        if not 0.001 <= value <= 3600:
            raise EngineeringValidationError("Die Simulationsdauer muss zwischen 1 ms und 3600 s liegen.")
        request.update(duration_s=value, observation_window={"mode": "EXPLICIT_REQUEST"})
    return request


def _explicit_duration(config):
    for owner, source in (("CONFIG", config), ("SCENARIO", config.get("scenario") or {}),
                          ("PARAMETERS", config.get("parameters") or {})):
        for key in ("duration_s", "duration"):
            if key not in source:
                continue
            value = _number(source[key])
            if value is None or not 0.001 <= value <= 3600:
                raise EngineeringValidationError("Die Simulationsdauer muss zwischen 1 ms und 3600 s liegen.")
            origin = (source.get("parameter_provenance") or {}).get(key) or {}
            if owner == "PARAMETERS" and origin.get("source") == "TECHNOLOGY_DEFAULT" and origin.get("value") == source[key]:
                continue
            return value, "EXPLICIT_" + owner
    return None, "DERIVED_REQUIREMENTS"


def _limit(route, config, *keys):
    for source in (route, route.get("timing") or {}, route.get("metadata") or {},
                   {**(config.get("parameters") or {}), **config}):
        for key in keys:
            if source.get(key) is not None:
                value = _number(source[key])
                return value if value is not None and value >= 0 else None
    return None


def _first_phase(route):
    segments = route.get("segments") or []
    if len(segments) > 1:
        first = segments[0]
        local = route if first.get("network_id") == route.get("network_id") else {}
        return first.get("phase_ms", local.get("phase_ms", 0))
    return route.get("phase_ms", 0)


def plan_observation_window(config: dict) -> dict:
    """Called once, after scope selection and physical release planning, at freeze."""
    mode = (config.get("observation_window") or {}).get("mode") or config.get("duration_mode")
    if mode not in AUTO_MODES:
        return config
    explicit, source = _explicit_duration(config)
    required_ms = 1000.0
    records, warnings = [], []
    communications = config.get("communications") or []
    for route in communications:
        identifier = str(route.get("routing_entry_id") or route.get("canonical_route_id") or route.get("id") or "")
        if _limit(route, config, "jitter_limit_ms", "maximum_jitter_ms", "jitter_ms") is None:
            continue
        contract = route.get("transmission_contract") or {}
        transmission_mode = str(contract.get("mode") or "CYCLIC").upper()
        if transmission_mode != "CYCLIC":
            warnings.append({"code": "OBSERVATION_NONCYCLIC_JITTER", "route_id": identifier,
                             "message": "Ereignis-/Anfrageverkehr braucht konkrete Freigaben; ein längeres Fenster erfindet keine zweite Übertragung."})
            continue
        # Runtime replaces a CYCLIC contract's period with the final cycle_ms.
        period = _number(route.get("cycle_ms") or route.get("period_ms") or contract.get("period_ms"))
        phase = _number(_first_phase(route))
        if period is None or period <= 0 or phase is None or phase < 0:
            warnings.append({"code": "OBSERVATION_RELEASE_UNKNOWN", "route_id": identifier,
                             "message": "Gültige finale Periode oder Quellphase fehlt."})
            continue
        bound = _limit(route, config, "maximum_latency_ms", "max_latency_ms", "deadline_ms")
        if bound is None:
            warnings.append({"code": "OBSERVATION_DELIVERY_BOUND_MISSING", "route_id": identifier,
                             "message": "Kein bestätigtes Ende-zu-Ende-Transportbudget für die zweite Ankunft vorhanden."})
            continue
        minimum = phase + period + bound + END_MARGIN_MS
        required_ms = max(required_ms, minimum)
        records.append({"route_id": identifier, "runtime_route_id": route.get("id"),
                        "source_phase_ms": phase, "period_ms": period, "delivery_budget_ms": bound,
                        "end_margin_ms": END_MARGIN_MS, "minimum_duration_s": minimum / 1000})
    if explicit is None and required_ms > 3_600_000:
        raise EngineeringValidationError("Automatischer Beobachtungsbedarf überschreitet 3600 s; Szenario explizit festlegen.")
    duration = explicit if explicit is not None else required_ms / 1000
    if explicit is not None and explicit * 1000 < required_ms:
        warnings.append({"code": "OBSERVATION_WINDOW_TOO_SHORT", "message": "Explizite Dauer bleibt erhalten; mindestens eine zweite Ankunft ist im geforderten Fenster nicht abgesichert."})
    # This is a lower bound on records: control traffic and faults can add more.
    # Preserve the caller's event budget; only actual result coverage can pass.
    release_records = 0
    for route in communications:
        if str((route.get("transmission_contract") or {}).get("mode") or "CYCLIC").upper() != "CYCLIC":
            continue
        period, phase = _number(route.get("cycle_ms")), _number(_first_phase(route))
        if period is not None and period > 0 and phase is not None:
            release_records += max(0, floor((duration * 1000 - phase) / period) + 1) * max(1, len(route.get("segments") or []))
    # Use the same environment-bound ceiling as the worker, without changing
    # an explicit request or presenting this lower bound as event completeness.
    from backend.app.simulation_service import DEFAULT_WORKFLOW_EVENT_LIMIT, _workflow_event_limit
    budget = config.get("max_events", DEFAULT_WORKFLOW_EVENT_LIMIT)
    normalized_budget = _number(budget)
    if isinstance(budget, bool) or normalized_budget is None or normalized_budget <= 0 or not normalized_budget.is_integer():
        raise EngineeringValidationError("Die Ereignisgrenze muss eine positive endliche ganze Zahl sein.")
    workflow_limit = _workflow_event_limit()
    effective_limit = min(int(normalized_budget), workflow_limit)
    if release_records > effective_limit:
        warnings.append({"code": "OBSERVATION_EVENT_BUDGET_INSUFFICIENT", "message": "Der Mindestbedarf überschreitet die unveränderte Ereignisgrenze; vollständige Beobachtung bleibt ungesichert."})
    return {**config, "duration_s": duration, "observation_window": {
        "version": 1, "mode": mode, "source": source, "status": "UNVERIFIED" if warnings else "PLANNED",
        "resolved_duration_s": duration, "requirement_minimum_duration_s": required_ms / 1000,
        "minimum_release_event_count": release_records, "event_count_basis": "CYCLIC_RELEASE_LOWER_BOUND",
        "requested_event_limit": int(normalized_budget), "workflow_event_limit": workflow_limit,
        "effective_event_limit": effective_limit, "routes": records, "warnings": warnings,
    }}
