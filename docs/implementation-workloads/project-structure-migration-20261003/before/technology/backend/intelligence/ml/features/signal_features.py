"""Feature extraction for signal semantics and model selection."""

from __future__ import annotations

from typing import Any

from ..core.feature_schema import FEATURE_SCHEMA_VERSION, FeatureSchema


SIGNAL_FEATURE_SCHEMA = FeatureSchema(
    task="SIGNAL_SEMANTIC_CLASSIFICATION",
    version=FEATURE_SCHEMA_VERSION,
    feature_names=(
        "name_token",
        "unit",
        "data_type",
        "bit_length",
        "minimum_bucket",
        "maximum_bucket",
        "has_enum",
        "enum_count",
        "producer_type",
        "cycle_bucket",
        "network_type",
    ),
)


def signal_features(signal: dict[str, Any]) -> dict[str, Any]:
    name = str(signal.get("display_name") or signal.get("name") or "")
    data = signal.get("data") if isinstance(signal.get("data"), dict) else {}
    communication = signal.get("communication") if isinstance(signal.get("communication"), dict) else {}
    enum_values = data.get("enum_values") if isinstance(data.get("enum_values"), dict) else {}
    protocol_bindings = signal.get("protocol_bindings") if isinstance(signal.get("protocol_bindings"), list) else []
    first_protocol = protocol_bindings[0] if protocol_bindings and isinstance(protocol_bindings[0], dict) else {}
    features = {
        "name_token": _dominant_token(name),
        "unit": str(signal.get("unit") or data.get("unit") or "").lower(),
        "data_type": str(signal.get("data_type") or signal.get("raw_datatype") or "").lower(),
        "bit_length": _number(signal.get("length_bits") or (signal.get("configuration") or {}).get("bit_length"), 0),
        "minimum_bucket": _bucket(_number(signal.get("min_value") or data.get("minimum"), 0)),
        "maximum_bucket": _bucket(_number(signal.get("max_value") or data.get("maximum"), 0)),
        "has_enum": bool(enum_values),
        "enum_count": len(enum_values),
        "producer_type": str(communication.get("producer_type") or communication.get("producer") or "").lower(),
        "cycle_bucket": _bucket(_number(communication.get("cycle_time_ms") or signal.get("cycle_ms"), 0)),
        "network_type": str(first_protocol.get("protocol") or signal.get("network_type") or "").lower(),
    }
    SIGNAL_FEATURE_SCHEMA.validate(features)
    return features


def status_features(signal: dict[str, Any]) -> dict[str, Any]:
    features = signal_features(signal)
    name = str(signal.get("display_name") or signal.get("name") or "").lower()
    features.update({
        "contains_status": "status" in name or "state" in name or "zustand" in name,
        "contains_health": "health" in name or "quality" in name or "error" in name,
    })
    return features


def physical_model_features(signal: dict[str, Any]) -> dict[str, Any]:
    return signal_features(signal)


def _dominant_token(value: str) -> str:
    tokens = [token for token in value.replace("_", " ").replace("-", " ").split() if token]
    lowered = " ".join(tokens).lower()
    for token in ("temperature", "temperatur", "rpm", "speed", "drehzahl", "pressure", "druck", "current", "strom", "voltage", "spannung", "position", "status", "state", "counter"):
        if token in lowered:
            return token
    return tokens[-1].lower() if tokens else ""


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bucket(value: float) -> str:
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    if value <= 1:
        return "tiny"
    if value <= 16:
        return "small"
    if value <= 100:
        return "medium"
    if value <= 1000:
        return "large"
    return "huge"
