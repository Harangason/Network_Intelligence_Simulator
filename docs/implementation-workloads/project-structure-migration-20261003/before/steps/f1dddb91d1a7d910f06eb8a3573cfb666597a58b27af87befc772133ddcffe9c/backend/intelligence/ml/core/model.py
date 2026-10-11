"""Small deterministic ensemble fallback used when sklearn is unavailable."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import log
from typing import Any


@dataclass
class EnsembleModel:
    model_id: str
    model_type: str
    task: str
    version: str
    feature_schema_version: str
    labels: tuple[str, ...]
    class_priors: dict[str, float]
    feature_weights: dict[str, dict[str, float]]
    feature_importances: dict[str, float] = field(default_factory=dict)

    def predict(self, features: dict[str, Any]) -> tuple[str, float, list[dict[str, Any]], list[dict[str, Any]]]:
        scores = {label: log(max(prior, 1e-9)) for label, prior in self.class_priors.items()}
        contributions: dict[str, float] = defaultdict(float)
        for feature, value in features.items():
            token = _feature_token(feature, value)
            weights = self.feature_weights.get(token, {})
            for label, weight in weights.items():
                scores[label] = scores.get(label, -20.0) + weight
                contributions[feature] += abs(weight)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        label, score = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else score - 1.0
        confidence = 1.0 / (1.0 + pow(2.718281828, -(score - runner_up)))
        alternatives = [{"label": item[0], "score": round(item[1], 4)} for item in ordered[1:4]]
        important = [
            {"feature": name, "importance": round(value, 4)}
            for name, value in sorted(contributions.items(), key=lambda item: item[1], reverse=True)[:8]
        ]
        return label, round(confidence, 4), alternatives, important

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "task": self.task,
            "version": self.version,
            "feature_schema_version": self.feature_schema_version,
            "labels": list(self.labels),
            "class_priors": self.class_priors,
            "feature_weights": self.feature_weights,
            "feature_importances": self.feature_importances,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnsembleModel":
        return cls(
            model_id=str(data["model_id"]),
            model_type=str(data["model_type"]),
            task=str(data["task"]),
            version=str(data["version"]),
            feature_schema_version=str(data["feature_schema_version"]),
            labels=tuple(str(item) for item in data.get("labels", [])),
            class_priors={str(k): float(v) for k, v in (data.get("class_priors") or {}).items()},
            feature_weights={str(k): {str(c): float(w) for c, w in v.items()} for k, v in (data.get("feature_weights") or {}).items()},
            feature_importances={str(k): float(v) for k, v in (data.get("feature_importances") or {}).items()},
        )


def train_token_ensemble(
    rows: list[dict[str, Any]],
    *,
    task: str,
    model_type: str,
    feature_schema_version: str,
    version: str = "1.0",
) -> EnsembleModel:
    class_counts = Counter(str(row["label"]) for row in rows)
    labels = tuple(sorted(class_counts))
    total = max(1, sum(class_counts.values()))
    priors = {label: (class_counts[label] + 1) / (total + len(labels)) for label in labels}
    token_counts: dict[str, Counter[str]] = defaultdict(Counter)
    token_totals = Counter()
    for row in rows:
        label = str(row["label"])
        for feature, value in (row.get("features") or {}).items():
            token = _feature_token(feature, value)
            token_counts[token][label] += 1
            token_totals[label] += 1
    weights: dict[str, dict[str, float]] = {}
    importances = Counter()
    smoothing = 0.75 if model_type == "GRADIENT_BOOSTING" else 1.0
    for token, counts in token_counts.items():
        row = {}
        token_total = sum(counts.values())
        for label in labels:
            p_token_label = (counts[label] + smoothing) / (token_totals[label] + smoothing * max(1, len(token_counts)))
            p_token = (token_total + smoothing) / (sum(token_totals.values()) + smoothing * max(1, len(token_counts)))
            row[label] = log(max(p_token_label / p_token, 1e-9))
            importances[token.split("=", 1)[0]] += abs(row[label])
        weights[token] = row
    return EnsembleModel(
        model_id=f"{task.lower()}-{model_type.lower()}-{version}",
        model_type=model_type,
        task=task,
        version=version,
        feature_schema_version=feature_schema_version,
        labels=labels,
        class_priors=priors,
        feature_weights=weights,
        feature_importances={k: round(v, 4) for k, v in importances.items()},
    )


def _feature_token(name: str, value: Any) -> str:
    if isinstance(value, bool):
        return f"{name}={int(value)}"
    if isinstance(value, (int, float)):
        return f"{name}={_bucket(float(value))}"
    text = str(value or "").strip().lower()
    return f"{name}={text}"


def _bucket(value: float) -> str:
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    if value <= 1:
        return "tiny"
    if value <= 8:
        return "small"
    if value <= 64:
        return "medium"
    if value <= 1000:
        return "large"
    return "huge"
