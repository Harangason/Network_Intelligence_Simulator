from __future__ import annotations

import json

import pytest

from backend.intelligence.ml.core.feature_schema import FEATURE_SCHEMA_VERSION
from backend.intelligence.ml.core.registry import ModelRegistry
from backend.intelligence.ml.inference.service import MLInferenceService


def _service(tmp_path):
    return MLInferenceService(registry=ModelRegistry(tmp_path))


def test_trains_random_forest_and_gradient_boosting_candidates(tmp_path):
    result = _service(tmp_path).train_task("SIGNAL_SEMANTIC_CLASSIFICATION")

    assert result["production_deployed"] is False
    assert result["deployment_policy"] == "REVIEW_GATE_REQUIRED"
    assert result["dataset"]["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert {candidate["model_type"] for candidate in result["candidates"]} == {"RANDOM_FOREST", "GRADIENT_BOOSTING"}
    assert result["preferred"]["status"] == "CANDIDATE"


def test_signal_classification_predicts_semantic_label(tmp_path):
    result = _service(tmp_path).classify_signal(
        {"name": "MotorTemperature", "unit": "degC", "data_type": "signed", "length_bits": 16, "min_value": -40, "max_value": 200}
    )

    assert result["label"] == "TEMPERATURE"
    assert result["confidence_policy"] in {"HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "REVIEW_REQUIRED"}
    assert result["classification_not_truth"] is True


def test_status_and_physical_model_selection(tmp_path):
    service = _service(tmp_path)

    status = service.classify_status({"name": "GatewayStatus", "unit": "code", "data": {"enum_values": {"OFF": 0, "READY": 3}}})
    physical = service.select_physical_model({"name": "MotorRPM", "unit": "rpm", "data_type": "unsigned", "length_bits": 16})

    assert status["label"] == "GATEWAY_STATUS_MODEL"
    assert physical["label"] == "physical/rotational_speed.py"


def test_fault_classification_detects_network_overload(tmp_path):
    result = _service(tmp_path).classify_fault({"bus_load": [{"load_percent": 95}], "faults": ["NETWORK_OVERLOAD"]})

    assert result["label"] == "NETWORK_OVERLOAD"


def test_route_ranking_excludes_invalid_routes_and_orders_valid(tmp_path):
    result = _service(tmp_path).rank_routes(
        [
            {"id": "slow", "valid": True, "path": ["ecu", "gateway", "bus"], "timing": {"latency_ms": 12, "jitter_ms": 2}, "network_load": 70},
            {"id": "invalid", "valid": False, "path": ["ecu"], "network_load": 5},
            {"id": "fast", "valid": True, "path": ["ecu", "bus"], "timing": {"latency_ms": 2, "jitter_ms": 0.2}, "network_load": 20},
        ]
    )

    assert [item["route_id"] for item in result["ranking"]] == ["fast", "slow"]
    assert result["note"] == "Nur validierte Routen wurden bewertet."


def test_packing_score_is_advisory_and_non_mutating(tmp_path):
    result = _service(tmp_path).score_packing({"payload_used_bits": 8, "payload_capacity_bits": 64, "busload": 12})

    assert result["label"] == "MERGE_RECOMMENDED"
    assert result["proposal_only"] is True
    assert result["may_mutate_payload"] is False
    assert result["deterministic_service"] == "MessagePackingService"


def test_architecture_score_marks_high_risk_as_classification_not_truth(tmp_path):
    result = _service(tmp_path).score_architecture(
        {"counts": {"routing_gaps": 4, "spof_count": 2, "timing_violations": 1, "unknown_semantics": 2}, "metrics": {"busload_margin": 3}}
    )

    assert result["label"] == "HIGH_RISK"
    assert result["classification_not_truth"] is True


def test_schema_mismatch_is_rejected(tmp_path):
    service = _service(tmp_path)
    service.train_task("SIGNAL_SEMANTIC_CLASSIFICATION")
    entry = service.registry.preferred("SIGNAL_SEMANTIC_CLASSIFICATION")
    artifact = entry["artifact_location"]
    data = json.loads(open(artifact, encoding="utf-8").read())
    data["feature_schema_version"] = "old-schema"
    with open(artifact, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

    with pytest.raises(ValueError, match="Feature-Schema mismatch"):
        service.classify_signal({"name": "MotorTemperature", "unit": "degC"})
