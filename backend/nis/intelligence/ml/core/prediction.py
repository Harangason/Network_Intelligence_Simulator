"""Prediction result model with confidence policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def confidence_band(confidence: float) -> str:
    if confidence >= 0.90:
        return "HIGH_CONFIDENCE"
    if confidence >= 0.70:
        return "MEDIUM_CONFIDENCE"
    return "REVIEW_REQUIRED"


@dataclass(frozen=True)
class MLPrediction:
    task: str
    label: str
    confidence: float
    model_type: str
    model_id: str
    feature_schema_version: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    important_features: list[dict[str, Any]] = field(default_factory=list)
    policy: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence_policy"] = confidence_band(self.confidence)
        return data
