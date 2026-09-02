from __future__ import annotations

import math
from typing import Any

from .registry import SafeFormula


SUPPORTED_BEHAVIOR_TYPES = {
    "CONSTANT", "STEP", "RAMP", "LINEAR", "SINE", "TRIANGLE", "SAWTOOTH",
    "PULSE", "RANDOM_WALK", "BOUNDED_RANDOM", "STATE_DEPENDENT", "FORMULA",
    "LOOKUP_TABLE", "EXTERNAL_SERIES", "PHYSICS_MODEL", "STATE_MACHINE", "STATUS_MODEL",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _identity_values(item: dict[str, Any]) -> set[str]:
    return {str(value) for value in (item.get("id"), item.get("name"), item.get("display_name")) if value}


def _behavior_for(signal: dict[str, Any], behaviors_by_signal: dict[str, dict[str, Any]]) -> dict[str, Any]:
    configuration = _mapping(signal.get("configuration"))
    return _mapping(signal.get("behavior")) or behaviors_by_signal.get(str(signal.get("id")), {}) or _mapping(configuration.get("behavior"))


def validate_signal_emulation_model(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the Python signal emulation contract before trace generation."""

    model = _mapping(config.get("engineering_model"))
    signals = [item for item in _sequence(model.get("signals")) if isinstance(item, dict)]
    messages = [item for item in _sequence(model.get("messages")) if isinstance(item, dict)]
    behaviors = [item for item in _sequence(model.get("behaviors")) if isinstance(item, dict)]
    communications = [item for item in _sequence(config.get("communications")) if isinstance(item, dict)]

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    behaviors_by_signal = {str(item.get("signal_id")): item for item in behaviors if item.get("signal_id")}
    signal_by_ref: dict[str, dict[str, Any]] = {}
    for signal in signals:
        for ref in _identity_values(signal):
            signal_by_ref[ref] = signal
    message_by_id = {str(item.get("id")): item for item in messages if item.get("id")}
    payload_bits_by_message: dict[str, int] = {}
    for communication in communications:
        payload_bits = max(1, int(_number(communication.get("payload_bytes"), 8))) * 8
        for message_id in _sequence(communication.get("message_ids")):
            payload_bits_by_message[str(message_id)] = payload_bits
        for signal_id in _sequence(communication.get("signal_ids")):
            signal = signal_by_ref.get(str(signal_id))
            if signal and signal.get("message_id"):
                payload_bits_by_message[str(signal.get("message_id"))] = payload_bits

    dependencies_by_signal: dict[str, set[str]] = {}
    formula_count = 0
    derived_count = 0
    generic_count = 0
    physics_count = 0

    def add_issue(target: list[dict[str, str]], code: str, message: str, signal: dict[str, Any] | None = None) -> None:
        target.append({
            "code": code,
            "message": message,
            **({"signal_id": str(signal.get("id") or ""), "signal": str(signal.get("name") or signal.get("id") or "")} if signal else {}),
        })

    for signal in signals:
        behavior = _behavior_for(signal, behaviors_by_signal)
        parameters = {**_mapping(signal.get("configuration")), **_mapping(behavior.get("parameters")), **behavior}
        behavior_type = str(behavior.get("behavior_type") or behavior.get("type") or "").upper()
        if not behavior_type:
            generic_count += 1
            add_issue(warnings, "SIGNAL_BEHAVIOR_MISSING", "Signal nutzt generische Fallback-Emulation.", signal)
        elif behavior_type not in SUPPORTED_BEHAVIOR_TYPES:
            add_issue(errors, "SIGNAL_BEHAVIOR_UNSUPPORTED", f"Behavior-Modell wird nicht unterstuetzt: {behavior_type}", signal)
        if behavior_type == "PHYSICS_MODEL":
            physics_count += 1
        if behavior_type in {"STATE_MACHINE", "STATUS_MODEL"}:
            derived_count += 0
        if behavior_type == "FORMULA":
            formula_count += 1
            try:
                SafeFormula.evaluate(str(parameters.get("formula") or "mid"), _formula_variables(signal_by_ref))
            except Exception as exc:
                add_issue(errors, "SIGNAL_FORMULA_INVALID", f"Formel ist nicht ausfuehrbar: {exc}", signal)

        dependency_refs = [str(item) for item in _sequence(behavior.get("dependencies") or signal.get("dependencies")) if str(item)]
        dependency_ids: set[str] = set()
        for dependency_ref in dependency_refs:
            dependency = signal_by_ref.get(dependency_ref)
            if dependency is None:
                add_issue(errors, "SIGNAL_DEPENDENCY_MISSING", f"Abhaengigkeit ist nicht aufloesbar: {dependency_ref}", signal)
                continue
            dependency_ids.add(str(dependency.get("id") or dependency_ref))
        if dependency_ids:
            derived_count += 1
        dependencies_by_signal[str(signal.get("id") or signal.get("name") or "")] = dependency_ids

        message_id = str(signal.get("message_id") or "")
        if message_id and message_id not in message_by_id:
            add_issue(errors, "SIGNAL_MESSAGE_MISSING", f"Message ist nicht aufloesbar: {message_id}", signal)
        payload_bits = payload_bits_by_message.get(message_id, int(_number(_mapping(message_by_id.get(message_id)).get("payload_bytes"), 8)) * 8)
        start_bit = max(0, int(_number(signal.get("start_bit"), 0)))
        length_bits = max(1, int(_number(signal.get("length_bits"), 16)))
        if start_bit + length_bits > payload_bits:
            add_issue(errors, "SIGNAL_ENCODING_OVERFLOW", f"Signal-Encoding endet bei Bit {start_bit + length_bits}, Payload hat {payload_bits} Bit.", signal)

    for cycle in _dependency_cycles(dependencies_by_signal):
        errors.append({
            "code": "SIGNAL_DEPENDENCY_CYCLE",
            "message": "Zyklische Signalabhaengigkeit: " + " -> ".join(cycle),
        })

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "signals": len(signals),
            "behaviors": len(behaviors),
            "formulas": formula_count,
            "derived_signals": derived_count,
            "physics_models": physics_count,
            "generic_fallbacks": generic_count,
        },
    }


def _formula_variables(signals_by_ref: dict[str, dict[str, Any]]) -> dict[str, float]:
    variables = {"t": 0.0, "min": 0.0, "max": 100.0, "mid": 50.0}
    for ref, signal in signals_by_ref.items():
        midpoint = (_number(signal.get("min_value"), 0.0) + _number(signal.get("max_value"), 100.0)) / 2.0
        variables[ref.replace("-", "_")] = midpoint
        variables[ref] = midpoint
    return variables


def _dependency_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            cycles.append([*stack[start:], node])
            return
        visiting.add(node)
        stack.append(node)
        for dependency in graph.get(node, set()):
            visit(dependency)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles
