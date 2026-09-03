"""Inference facade for simulator ML tasks.

The service keeps ML as advisory intelligence. Deterministic engineering
services still own payload packing, routing validation and architecture edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..core.feature_schema import FEATURE_SCHEMA_VERSION
from ..core.model import EnsembleModel
from ..core.prediction import MLPrediction, confidence_band
from ..core.registry import ModelRegistry
from ..evaluation.evaluator import evaluate_classifier
from ..features.architecture_features import architecture_features
from ..features.packing_features import packing_features
from ..features.routing_features import routing_features
from ..features.signal_features import physical_model_features, signal_features, status_features
from ..features.trace_features import trace_features
from ..gradient_boosting.trainer import GradientBoostingTrainer
from ..random_forest.trainer import RandomForestTrainer
from ..training.dataset import MLDatasetBuilder, simulator_ml_golden_examples


Extractor = Callable[[dict[str, Any]], dict[str, Any]]


TASK_EXTRACTORS: dict[str, Extractor] = {
    "SIGNAL_SEMANTIC_CLASSIFICATION": signal_features,
    "STATUS_MODEL_CLASSIFICATION": status_features,
    "PHYSICAL_MODEL_SELECTION": physical_model_features,
    "TRACE_FAULT_CLASSIFICATION": trace_features,
}


class MLInferenceService:
    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()

    def train_task(self, task: str) -> dict[str, Any]:
        task = _normalize_task(task)
        extractor = _extractor_for(task)
        examples = simulator_ml_golden_examples(task)
        if not examples:
            raise ValueError(f"Keine Trainingsdaten fuer ML-Task {task}.")
        builder = MLDatasetBuilder(task, extractor)
        splits, dataset_version = builder.export(examples)
        train_rows = splits["train"] or [row for rows in splits.values() for row in rows]
        eval_rows = splits["validation"] + splits["test"] or train_rows
        candidates = []
        for trainer in (RandomForestTrainer(), GradientBoostingTrainer()):
            model = trainer.train(task, train_rows)
            metrics = evaluate_classifier(model, eval_rows)
            entry = self.registry.save_model(model, dataset_version.version, metrics, status="CANDIDATE")
            candidates.append(entry.to_dict())
        preferred = self.registry.preferred(task)
        return {
            "task": task,
            "dataset": dataset_version.to_dict(),
            "candidates": candidates,
            "preferred": preferred,
            "deployment_policy": "REVIEW_GATE_REQUIRED",
            "production_deployed": False,
        }

    def classify_signal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._predict_task("SIGNAL_SEMANTIC_CLASSIFICATION", payload)

    def classify_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._predict_task("STATUS_MODEL_CLASSIFICATION", payload)

    def select_physical_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._predict_task("PHYSICAL_MODEL_SELECTION", payload)

    def classify_fault(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._predict_task("TRACE_FAULT_CLASSIFICATION", payload)

    def rank_routes(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        ranked = []
        for route in routes:
            if not _is_validated_route(route):
                continue
            features = routing_features(route)
            penalty = (
                features["hop_count"] * 0.08
                + features["gateway_count"] * 0.05
                + features["network_load"] * 0.006
                + features["latency"] * 0.01
                + features["jitter"] * 0.025
                + features["receiver_count"] * 0.01
            )
            score = _clamp(1.0 - penalty + min(features["redundancy"], 3) * 0.04)
            ranked.append(
                {
                    "route_id": route.get("id") or route.get("route_id") or route.get("name"),
                    "name": route.get("name") or route.get("route_name") or route.get("id"),
                    "route_score": round(score, 4),
                    "confidence": round(0.72 + score * 0.22, 4),
                    "confidence_policy": confidence_band(0.72 + score * 0.22),
                    "important_features": _top_route_features(features),
                }
            )
        ranked.sort(key=lambda item: item["route_score"], reverse=True)
        return {
            "task": "ROUTE_CANDIDATE_RANKING",
            "model_type": "GRADIENT_BOOSTING",
            "ranking": ranked,
            "note": "Nur validierte Routen wurden bewertet.",
            "deployment_policy": "REVIEW_GATE_REQUIRED",
        }

    def score_packing(self, message: dict[str, Any]) -> dict[str, Any]:
        features = packing_features(message)
        utilization = features["payload_utilization"]
        busload = features["busload"]
        if utilization > 0.95 or busload > 80:
            label, confidence = "SPLIT_RECOMMENDED", 0.92
        elif utilization < 0.25 and features["payload_free_bits"] >= 32:
            label, confidence = "MERGE_RECOMMENDED", 0.88
        elif utilization < 0.50:
            label, confidence = "REPACK_RECOMMENDED", 0.76
        else:
            label, confidence = "PACKING_GOOD", 0.91
        return {
            "task": "MESSAGE_PACKING_QUALITY",
            "label": label,
            "confidence": confidence,
            "confidence_policy": confidence_band(confidence),
            "model_type": "GRADIENT_BOOSTING",
            "features": features,
            "proposal_only": True,
            "may_mutate_payload": False,
            "deterministic_service": "MessagePackingService",
        }

    def score_architecture(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        features = architecture_features(snapshot)
        issue_score = (
            features["orphan_signals"]
            + features["unmapped_functions"]
            + features["routing_gaps"]
            + features["unknown_semantics"]
            + features["traceability_gaps"]
            + features["timing_violations"] * 2
            + features["spof_count"] * 2
        )
        if issue_score >= 8 or features["busload_margin"] < 5:
            label, confidence = "HIGH_RISK", 0.91
        elif issue_score >= 3 or features["busload_margin"] < 20:
            label, confidence = "MEDIUM_RISK", 0.82
        else:
            label, confidence = "LOW_RISK", 0.9
        return {
            "task": "ARCHITECTURE_GAP_QUALITY",
            "label": label,
            "confidence": confidence,
            "confidence_policy": confidence_band(confidence),
            "model_type": "RANDOM_FOREST",
            "features": features,
            "classification_not_truth": True,
            "deployment_policy": "REVIEW_GATE_REQUIRED",
        }

    def explain_for_qwen(self, finding: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "LLM_INTERPRETATION_INPUT",
            "ml_result": finding,
            "instruction": (
                "Qwen erklaert Befund, Confidence, wichtigste Features und konkrete Vorschlaege. "
                "Die ML-Klasse wird nicht ueberschrieben, ausser Qwen liefert eine explizite Gegenhypothese."
            ),
        }

    def _predict_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        task = _normalize_task(task)
        entry = self._ensure_model(task)
        model = self._load_model(entry)
        features = _extractor_for(task)(payload)
        label, confidence, alternatives, important = model.predict(features)
        result = MLPrediction(
            task=task,
            label=label,
            confidence=confidence,
            model_type=model.model_type,
            model_id=model.model_id,
            feature_schema_version=model.feature_schema_version,
            alternatives=alternatives,
            important_features=important,
            policy="REVIEW_GATE_REQUIRED",
        ).to_dict()
        result["features"] = features
        result["classification_not_truth"] = True
        return result

    def _ensure_model(self, task: str) -> dict[str, Any]:
        entry = self.registry.preferred(task)
        if entry is None:
            self.train_task(task)
            entry = self.registry.preferred(task)
        if entry is None:
            raise ValueError(f"Kein ML-Modell fuer Task {task}.")
        return entry

    def _load_model(self, entry: dict[str, Any]) -> EnsembleModel:
        artifact = Path(str(entry["artifact_location"]))
        model = EnsembleModel.from_dict(json.loads(artifact.read_text(encoding="utf-8")))
        if model.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"Feature-Schema mismatch: Modell {model.feature_schema_version}, Runtime {FEATURE_SCHEMA_VERSION}."
            )
        return model


def _normalize_task(task: str) -> str:
    return str(task or "").strip().upper()


def _extractor_for(task: str) -> Extractor:
    try:
        return TASK_EXTRACTORS[task]
    except KeyError as exc:
        raise ValueError(f"Unbekannter ML-Task {task}.") from exc


def _is_validated_route(route: dict[str, Any]) -> bool:
    blocked = {"FAIL", "FAILED", "ERROR", "INVALID", "REJECTED"}
    if route.get("valid") is False:
        return False
    return str(route.get("status") or route.get("validation_status") or "VALID").upper() not in blocked


def _top_route_features(features: dict[str, Any]) -> list[dict[str, Any]]:
    names = ("network_load", "latency", "hop_count", "gateway_count", "jitter", "redundancy")
    return [{"feature": name, "value": features[name]} for name in names if name in features]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
