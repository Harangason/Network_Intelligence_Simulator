from __future__ import annotations

import pytest

from agent_core.api import WORKLOAD_API_ROUTES
from agent_core.context import ContextBuilder
from agent_core.core import DependencyState, EngineeringWorkload, WorkPackage, WorkloadDependencyGraph
from agent_core.errors import AgentCoreValidationError, RegistryLookupError
from agent_core.generators import GeneratorResult
from agent_core.orchestration import (
    RetryManager,
    WorkloadDispatcher,
    WorkloadExecutionLoop,
    WorkloadPlanner,
    WorkloadProgressTracker,
)
from agent_core.persistence import AuditEvent, InMemoryAuditRepository
from agent_core.proposals import ApprovalBoundary, InMemoryProposalStore, Proposal, ProposalStatus
from agent_core.registry import GeneratorRegistry, HandlerRegistry, ToolRegistry, ValidatorRegistry
from agent_core.repair import MissingWorkService, RegenerationService, RepairService
from agent_core.validation import CompletionValidator, DuplicateValidator, QualityValidator, WorkloadValidator


def _packages(thermal: int = 10, motion: int = 25) -> list[dict]:
    return [
        {
            "package_code": "WP-TEMP",
            "category": "thermal",
            "target_object": "Signal",
            "requested_count": 10,
            "generated_count": thermal,
            "valid_count": thermal,
            "invalid_count": 0,
            "duplicate_count": 0,
            "status": "IN_PROGRESS",
        },
        {
            "package_code": "WP-MOTION",
            "category": "motion",
            "target_object": "Signal",
            "requested_count": 25,
            "generated_count": motion,
            "valid_count": motion,
            "invalid_count": 0,
            "duplicate_count": 0,
            "status": "IN_PROGRESS",
        },
    ]


def _objects(count: int, *, approved: bool = False) -> list[dict]:
    return [
        {
            "workload_object_id": str(index),
            "is_valid": True,
            "is_duplicate": False,
            "proposal_id": None if approved else "proposal-1",
            "canonical_id": str(index) if approved else None,
            "review_state": "REVIEWED" if approved else "READY_FOR_REVIEW",
            "approval_state": "APPROVED" if approved else "PENDING",
            "validation_results": [],
        }
        for index in range(count)
    ]


def test_workload_and_work_package_creation_enforce_exact_targets():
    packages = [
        WorkPackage("WP-TEMP", "thermal", "Signal", 10),
        WorkPackage("WP-MOTION", "motion", "Signal", 25),
    ]
    workload = EngineeringWorkload("w-1", "SIGNAL_GENERATION", "35 signals", 35, packages)

    assert workload.target_total == 35
    assert [item.requested_count for item in workload.work_packages] == [10, 25]
    with pytest.raises(AgentCoreValidationError, match="WORKLOAD_CONFIGURATION_ERROR"):
        EngineeringWorkload("w-2", "SIGNAL_GENERATION", "bad", 35, packages[:1])


def test_planner_uses_injected_parser_and_preserves_subtargets():
    planner = WorkloadPlanner(lambda prompt, payload: {**payload, "prompt": prompt, "requested_total": 35})
    result = planner.plan({"prompt": "35 signals", "work_packages": _packages()})

    assert result["requested_total"] == 35
    assert len(result["work_packages"]) == 2


def test_target_and_subtarget_validation_are_separate_checks():
    validator = CompletionValidator()
    packages = _packages(thermal=9, motion=25)
    workload = {"requested_total": 35}

    assert validator.evaluate_total_target(workload, packages) is False
    assert validator.evaluate_sub_targets(packages) is False
    assert WorkloadValidator().validate({"requested_total": 35}, packages) == []


def test_dependency_resolution_reports_ready_waiting_blocked_and_order():
    graph = WorkloadDependencyGraph()
    graph.add_dependency("signals", "interfaces")
    graph.add_dependency("interfaces", "hardware")

    assert graph.execution_order() == ["hardware", "interfaces", "signals"]
    assert graph.readiness("signals", {"interfaces": "IN_PROGRESS"}).state == DependencyState.WAITING
    assert graph.readiness("signals", {"interfaces": "FAILED"}).state == DependencyState.BLOCKED
    assert graph.readiness("signals", {"interfaces": "COMPLETED"}).state == DependencyState.READY


def test_dependency_cycle_is_rejected():
    graph = WorkloadDependencyGraph()
    graph.add_dependency("a", "b")
    with pytest.raises(AgentCoreValidationError, match="cycle"):
        graph.add_dependency("b", "a")


def test_dispatcher_selects_registered_handler_generator_and_validator():
    handler, generator, validator = object(), object(), object()
    handlers, generators, validators = HandlerRegistry(), GeneratorRegistry(), ValidatorRegistry()
    handlers.register(handler, "CUSTOM")
    generators.register(generator, "CUSTOM", "thermal")
    validators.register(validator, "CUSTOM", "quality")

    selection = WorkloadDispatcher(handlers, generators, validators).dispatch("CUSTOM", "thermal")

    assert selection.handler is handler
    assert selection.generator is generator
    assert selection.validators == (validator,)
    with pytest.raises(RegistryLookupError):
        generators.get("CUSTOM", "motion")


def test_tool_registry_lists_names_and_filters_registered_tools():
    registry = ToolRegistry()
    registry.register("analyze.capacity", {"category": "analysis"})
    registry.register("import.intelligent", {"category": "import"})

    assert registry.names() == ("analyze.capacity", "import.intelligent")
    assert registry.list()[0]["category"] == "analysis"
    assert registry.filter(lambda tool: tool["category"] == "import") == ({"category": "import"},)


def test_generator_contract_validates_counts_and_is_not_completion():
    result = GeneratorResult("SUCCESS", requested=10, generated=10, valid=9, invalid=1, remaining=1)

    assert result.as_dict()["remaining"] == 1
    assert "task_complete" not in result.as_dict()
    with pytest.raises(AgentCoreValidationError):
        GeneratorResult("SUCCESS", requested=1, generated=1, valid=1, invalid=1)


def test_validation_failure_reports_missing_required_field():
    findings = QualityValidator(("name", "unit")).validate({"name": "MotorRPM"})

    assert findings == [{"code": "MISSING_FIELD", "field": "unit", "severity": "ERROR"}]


def test_duplicate_detection_covers_id_name_semantic_alias_and_near_match():
    aliases = {"motorrpm": "rotation", "enginespeed": "rotation"}
    validator = DuplicateValidator(aliases=aliases, near_threshold=0.85)
    findings = validator.validate(
        [
            {"id": "one", "name": "MotorRPM"},
            {"id": "two", "name": "EngineSpeed"},
            {"id": "three", "name": "WheelSpead"},
            {"id": "four", "name": "WheelSpeed"},
            {"id": "four", "name": "Unique"},
        ]
    )

    assert {item["code"] for item in findings} >= {"POSSIBLE_DUPLICATE", "NEAR_DUPLICATE", "DUPLICATE_ID"}


def test_automatic_repair_uses_registered_safe_strategy():
    service = RepairService()
    service.register("UNIT_MISMATCH", lambda item, context: {**item, "unit": context["expected_unit"]})
    result = service.repair(
        [{"id": "rpm", "unit": "km/h", "validation_results": [{"code": "UNIT_MISMATCH"}]}],
        {"expected_unit": "rpm"},
    )

    assert result["repaired_count"] == 1
    assert result["repaired"][0]["unit"] == "rpm"


def test_missing_work_regeneration_requests_only_the_gap():
    missing = MissingWorkService().detect(_packages(thermal=9, motion=25))

    class FakeGenerator:
        def generate(self, requested, **kwargs):
            return GeneratorResult("SUCCESS", requested=requested, generated=requested, objects=[{"id": "new"}])

    result = RegenerationService().regenerate(
        missing[0], FakeGenerator(), {"workload_id": "w"}, _packages()[0], {}
    )

    assert missing[0].count == 1
    assert result.requested == result.generated == 1


def test_retry_limit_is_bounded_and_explainable():
    manager = RetryManager(max_attempts=2)
    state = manager.record_attempt("w", reason="MISSING_WORK")
    state = manager.record_attempt("w", reason="VALIDATION_FAILED", error="bad unit")

    assert state.exhausted is True
    assert state.attempt_count == 2
    assert state.last_error == "bad unit"
    assert manager.terminal_status(blocked=False) == "INCOMPLETE"


def test_progress_calculation_reports_package_and_overall_counts():
    progress = WorkloadProgressTracker().calculate({"requested_total": 35}, _packages(thermal=9, motion=22))

    assert progress["valid"] == 31
    assert progress["missing"] == 4
    assert progress["percent"] == pytest.approx(88.57)
    assert progress["work_packages"][0]["missing_count"] == 1


def test_completion_is_ready_for_review_then_completed_after_approval():
    validator = CompletionValidator()
    workload = {"requested_total": 35, "attempts": 1, "max_generation_attempts": 3}

    review = validator.evaluate(workload, _packages(), _objects(35), [])
    completed = validator.evaluate(workload, _packages(), _objects(35, approved=True), [])

    assert review["status"] == "READY_FOR_REVIEW"
    assert review["task_complete"] is False
    assert completed["status"] == "COMPLETED"
    assert completed["task_complete"] is True


def test_parent_completion_requires_all_mandatory_children():
    graph = WorkloadDependencyGraph()
    graph.add_child("parent", "hardware")
    graph.add_child("parent", "signals")

    assert graph.parent_complete("parent", {"hardware": "COMPLETED", "signals": "READY_FOR_REVIEW"}) is False
    assert graph.parent_complete("parent", {"hardware": "COMPLETED", "signals": "COMPLETED"}) is True


def test_proposal_creation_and_human_approval_boundary():
    store = InMemoryProposalStore()
    proposal = store.save(Proposal("p-1", "w-1", [{"name": "Signal"}], ProposalStatus.READY_FOR_REVIEW))
    boundary = ApprovalBoundary(store)

    assert proposal.status == ProposalStatus.READY_FOR_REVIEW
    with pytest.raises(AgentCoreValidationError, match="Human approval"):
        boundary.approve("p-1", actor="agent-orchestrator")
    assert boundary.approve("p-1", actor="martin").status == ProposalStatus.APPROVED


def test_audit_repository_preserves_actor_model_generator_and_before_after():
    repository = InMemoryAuditRepository()
    event = AuditEvent(
        "w-1",
        "GENERATOR_EXECUTED",
        actor="martin",
        model="model-1",
        generator="TemperatureSignalGenerator",
        before={"valid": 9},
        after={"valid": 10},
    )
    repository.append(event)

    assert repository.list("w-1") == [event]


def test_context_builder_keeps_engineering_rag_and_graph_separate():
    builder = ContextBuilder(
        engineering_provider=lambda workload, package: {"project_id": "p-1"},
        rag_provider=lambda workload, package: {"approved_objects": ["s-1"]},
        graph_provider=lambda workload, package: {"neighbors": ["ecu-1"]},
    )
    context = builder.build({"workload_id": "w-1"}, {"work_package_id": "wp-1"}).as_dict()

    assert context["engineering"]["project_id"] == "p-1"
    assert context["rag"]["approved_objects"] == ["s-1"]
    assert context["graph"]["neighbors"] == ["ecu-1"]


def test_execution_loop_stops_at_retry_limit_without_infinite_loop():
    state = {"status": "IN_PROGRESS", "attempts": 0, "max_generation_attempts": 2, "dependencies_resolved": [], "valid_count": 0}

    def execute(current):
        current["attempts"] += 1

    def evaluate():
        return {"status": "INCOMPLETE" if state["attempts"] >= 2 else "IN_PROGRESS"}

    result = WorkloadExecutionLoop().run(
        inspect=lambda: state,
        execute_cycle=execute,
        evaluate=evaluate,
        progress_token=lambda current: current["valid_count"],
    )

    assert result["status"] == "INCOMPLETE"
    assert state["attempts"] == 2


def test_standard_api_inventory_contains_dependencies_and_audit():
    assert ("GET", "/workloads/{id}/dependencies") in WORKLOAD_API_ROUTES
    assert ("GET", "/workloads/{id}/audit") in WORKLOAD_API_ROUTES
