from __future__ import annotations

import pytest

from engineering.models import EngineeringValidationError
from engineering.workloads.handlers import (
    MOTION_SIGNAL_CATALOG,
    SignalGenerationWorkloadHandler,
    THERMAL_SIGNAL_CATALOG,
    semantic_alias_key,
    validate_signal_definition,
)
from engineering.workloads.models import evaluate_workload_completion, parse_workload_request


def _packages(*, valid_thermal: int, valid_motion: int, status: str = "IN_PROGRESS"):
    return [
        {
            "work_package_id": "thermal",
            "category": "thermal",
            "requested_count": 10,
            "generated_count": valid_thermal,
            "valid_count": valid_thermal,
            "invalid_count": 0,
            "duplicate_count": 0,
            "attempts": 1,
            "max_generation_attempts": 3,
            "status": status,
        },
        {
            "work_package_id": "motion",
            "category": "motion",
            "requested_count": 25,
            "generated_count": valid_motion,
            "valid_count": valid_motion,
            "invalid_count": 0,
            "duplicate_count": 0,
            "attempts": 1,
            "max_generation_attempts": 3,
            "status": status,
        },
    ]


def _objects(count: int, *, approved: bool = False):
    return [
        {
            "workload_object_id": str(index),
            "is_valid": True,
            "is_duplicate": False,
            "proposal_id": "proposal" if not approved else None,
            "canonical_id": str(index) if approved else None,
            "review_state": "REVIEWED" if approved else "READY_FOR_REVIEW",
            "approval_state": "APPROVED" if approved else "PENDING",
            "validation_results": [],
        }
        for index in range(count)
    ]


def test_manifest_example_is_split_into_exact_work_packages():
    plan = parse_workload_request(
        "Erzeuge insgesamt 35 Signale, 10 fuer Temperatur und 25 fuer Motion."
    )

    assert plan["workload_type"] == "SIGNAL_GENERATION"
    assert plan["requested_total"] == 35
    assert [(item["category"], item["requested_count"]) for item in plan["work_packages"]] == [
        ("thermal", 10),
        ("motion", 25),
    ]


def test_mismatching_total_and_packages_is_configuration_error():
    with pytest.raises(EngineeringValidationError, match="WORKLOAD_CONFIGURATION_ERROR"):
        parse_workload_request(
            "Erzeuge insgesamt 35 Signale.",
            {
                "workload_type": "SIGNAL_GENERATION",
                "requested_total": 35,
                "work_packages": [
                    {"category": "thermal", "requested_count": 10},
                    {"category": "motion", "requested_count": 24},
                ],
            },
        )


def test_generator_success_does_not_mean_task_complete():
    workload = {
        "requested_total": 35,
        "status": "VALIDATING",
        "attempts": 1,
        "max_generation_attempts": 3,
    }
    decision = evaluate_workload_completion(
        workload,
        _packages(valid_thermal=9, valid_motion=22),
        _objects(31),
    )

    assert decision["technical_success"] is True
    assert decision["task_complete"] is False
    assert decision["status"] == "IN_PROGRESS"
    assert decision["valid_count"] == 31
    assert decision["missing_count"] == 4


def test_all_valid_drafts_are_ready_for_review_but_not_completed():
    workload = {
        "requested_total": 35,
        "status": "VALIDATING",
        "attempts": 1,
        "max_generation_attempts": 3,
    }
    decision = evaluate_workload_completion(
        workload,
        _packages(valid_thermal=10, valid_motion=25, status="READY_FOR_REVIEW"),
        _objects(35),
    )

    assert decision["status"] == "READY_FOR_REVIEW"
    assert decision["ready_for_review"] is True
    assert decision["complete"] is False


def test_completed_requires_approved_canonical_objects():
    workload = {
        "requested_total": 35,
        "status": "VALIDATING",
        "attempts": 1,
        "max_generation_attempts": 3,
    }
    decision = evaluate_workload_completion(
        workload,
        _packages(valid_thermal=10, valid_motion=25, status="COMPLETED"),
        _objects(35, approved=True),
    )

    assert decision["status"] == "COMPLETED"
    assert decision["task_complete"] is True


def test_unsatisfied_dependency_blocks_completion():
    workload = {
        "requested_total": 35,
        "status": "VALIDATING",
        "attempts": 1,
        "max_generation_attempts": 3,
    }
    decision = evaluate_workload_completion(
        workload,
        _packages(valid_thermal=10, valid_motion=25),
        _objects(35),
        [{"satisfied": False}],
    )

    assert decision["status"] == "BLOCKED"


def test_signal_catalogs_match_manifest_targets_without_duplicate_names():
    assert len(THERMAL_SIGNAL_CATALOG) == 10
    assert len(MOTION_SIGNAL_CATALOG) == 25
    names = [item["name"].lower() for item in (*THERMAL_SIGNAL_CATALOG, *MOTION_SIGNAL_CATALOG)]
    assert len(names) == len(set(names)) == 35


def test_semantic_aliases_share_duplicate_detection_key():
    assert semantic_alias_key("MotorRPM") == semantic_alias_key("EngineSpeed")
    assert semantic_alias_key("TemperatureCurrent") == semantic_alias_key("ActualTemperature")


def test_handler_contract_exposes_structured_progress_and_completion():
    class FakeOrchestrator:
        @staticmethod
        def progress(workload_id):
            assert workload_id == "workload-1"
            return {"status": "COMPLETED", "valid": 35, "requested": 35}

    handler = SignalGenerationWorkloadHandler()
    workload = {"workload_id": "workload-1"}

    assert handler.get_progress(FakeOrchestrator(), workload)["valid"] == 35
    assert handler.is_complete(FakeOrchestrator(), workload) is True


def test_signal_minimum_fields_block_invalid_candidate():
    findings = validate_signal_definition(
        {
            "id": "signal-1",
            "name": "TemperatureCurrent",
            "description": "Current temperature",
            "category": "thermal",
            "datatype": "signed",
            "unit": "degC",
            "minimum": -40,
            "maximum": 180,
            "resolution": 0.1,
            "default_value": 0,
            "invalid_value": 181,
            "cycle_time": 10,
            "producer": "Thermal-ECU",
            "consumers": [],
            "source": "ai_generated",
            "generated_by": "test",
            "confidence": 0.9,
            "review_state": "unreviewed",
        }
    )

    assert {item.get("field") for item in findings} == {"display_name"}


def test_structured_non_signal_workload_uses_same_package_model():
    plan = parse_workload_request(
        "Erzeuge 8 Messages: 3 Thermal, 5 Motion.",
        {"workload_type": "MESSAGE_GENERATION", "requested_total": 8},
    )

    assert plan["workload_type"] == "MESSAGE_GENERATION"
    assert sum(item["requested_count"] for item in plan["work_packages"]) == 8
