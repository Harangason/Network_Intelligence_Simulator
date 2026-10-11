from __future__ import annotations

from enum import StrEnum


class SignalModelType(StrEnum):
    PHYSICS_BASED = "PHYSICS_BASED"
    RULE_BASED = "RULE_BASED"
    EMPIRICAL = "EMPIRICAL"
    SYNTHETIC = "SYNTHETIC"
    GENERIC_ESTIMATE = "GENERIC_ESTIMATE"


SYNTHETIC_BEHAVIORS = {
    "CONSTANT",
    "STEP",
    "RAMP",
    "LINEAR",
    "SINE",
    "TRIANGLE",
    "SAWTOOTH",
    "PULSE",
    "RANDOM_WALK",
    "BOUNDED_RANDOM",
}


PHYSICAL_SEMANTICS = {
    "NUMERIC",
    "NUMERIC_PHYSICAL",
    "TEMPERATURE",
    "SPEED",
    "RPM",
    "TORQUE",
    "PRESSURE",
    "VOLTAGE",
    "CURRENT",
    "POSITION",
    "VELOCITY",
    "ACCELERATION",
}


def normalize_model_type(value: object, *, behavior_type: str = "", semantic_type: str = "") -> str:
    candidate = str(value or "").upper()
    if candidate in {item.value for item in SignalModelType}:
        return candidate
    behavior = behavior_type.upper()
    semantic = semantic_type.upper()
    if behavior in SYNTHETIC_BEHAVIORS:
        return SignalModelType.SYNTHETIC.value
    if behavior in {"FORMULA", "STATE_DEPENDENT", "LOOKUP_TABLE", "EXTERNAL_SERIES", "STATE_MACHINE", "STATUS_MODEL"}:
        return SignalModelType.RULE_BASED.value
    if behavior == "PHYSICS_MODEL" or semantic in PHYSICAL_SEMANTICS:
        return SignalModelType.PHYSICS_BASED.value
    return SignalModelType.GENERIC_ESTIMATE.value
