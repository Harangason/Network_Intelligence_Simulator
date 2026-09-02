from __future__ import annotations

from typing import Any

from ..states import HEALTH_CODES, QUALITY_CODES, SAFETY_CODES, StateMachineEngine, health_from_context, quality_at, safety_from_health


def _code(mapping: dict[str, int], state: str) -> float:
    return float(mapping.get(state, 0))


def status_dimension(signal: Any) -> str:
    haystack = f"{signal.name} {signal.parameters.get('semantic_type') or ''}".lower()
    if "health" in haystack:
        return "HEALTH"
    if "safety" in haystack:
        return "SAFETY"
    if "quality" in haystack:
        return "QUALITY"
    if "communicat" in haystack or "link" in haystack or "bus" in haystack:
        return "COMMUNICATION"
    if "counter" in haystack or "alive" in haystack:
        return "COUNTER"
    if "enabled" in haystack or "valid" in haystack or signal.length_bits == 1:
        return "BOOLEAN"
    return "OPERATING"


def state_code(signal: Any, context: Any, state_name: str, states: tuple[str, ...]) -> float:
    enum = getattr(signal, "enum_values", {}) or {}
    if enum:
        return float(enum.get(state_name, enum.get(state_name.lower(), 0)))
    return float(states.index(state_name) if state_name in states else 0)


def health(signal: Any, _time_s: float, context: Any, _state: Any) -> float:
    return _code(HEALTH_CODES, health_from_context({"signal_values": getattr(context, "signal_values", {})}))


def safety(signal: Any, _time_s: float, context: Any, _state: Any) -> float:
    health_state = health_from_context({"signal_values": getattr(context, "signal_values", {})})
    return _code(SAFETY_CODES, safety_from_health(health_state))


def quality(signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    return _code(QUALITY_CODES, quality_at(time_s))


def operating(signal: Any, time_s: float, context: Any, _state: Any, engine: StateMachineEngine) -> float:
    state_name = engine.state_at(time_s, {"signal_values": getattr(context, "signal_values", {})})
    getattr(context, "system_state", {})["operating_state"] = state_name
    return state_code(signal, context, state_name, engine.allowed_states)
