"""Common evaluation for Random Forest and Gradient Boosting candidates."""

from __future__ import annotations

from collections import Counter
from typing import Any


def evaluate_classifier(model: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "confusion_matrix": {}, "inference_latency_ms": 0.0, "model_size": len(str(model.to_dict()))}
    labels = sorted({str(row["label"]) for row in rows})
    confusion: dict[str, Counter[str]] = {label: Counter() for label in labels}
    correct = 0
    for row in rows:
        expected = str(row["label"])
        predicted = model.predict(row["features"])[0]
        confusion.setdefault(expected, Counter())[predicted] += 1
        correct += int(predicted == expected)
    precision_values = []
    recall_values = []
    for label in labels:
        tp = confusion.get(label, Counter()).get(label, 0)
        fp = sum(counter.get(label, 0) for other, counter in confusion.items() if other != label)
        fn = sum(count for predicted, count in confusion.get(label, Counter()).items() if predicted != label)
        precision_values.append(tp / max(1, tp + fp))
        recall_values.append(tp / max(1, tp + fn))
    precision = sum(precision_values) / max(1, len(precision_values))
    recall = sum(recall_values) / max(1, len(recall_values))
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "accuracy": round(correct / len(rows), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion_matrix": {label: dict(counter) for label, counter in confusion.items()},
        "inference_latency_ms": 0.0,
        "model_size": len(str(model.to_dict())),
    }
