from __future__ import annotations

from typing import Any, Callable

from ..context.context_builder import ContextBuilder
from ..repair.missing_work_service import MissingWorkService
from ..repair.regeneration_service import RegenerationService
from ..repair.repair_service import RepairService
from ..validation.completion_validator import CompletionValidator
from .dispatcher import WorkloadDispatcher
from .planner import WorkloadPlanner
from .progress_tracker import WorkloadProgressTracker


class EngineeringWorkloadOrchestrator:
    """Generic facade that composes services and never creates domain objects."""

    def __init__(
        self,
        *,
        planner: WorkloadPlanner,
        dispatcher: WorkloadDispatcher,
        context_builder: ContextBuilder | None = None,
        completion_validator: CompletionValidator | None = None,
        repair_service: RepairService | None = None,
        regeneration_service: RegenerationService | None = None,
        missing_work_service: MissingWorkService | None = None,
        progress_tracker: WorkloadProgressTracker | None = None,
    ) -> None:
        self.planner = planner
        self.dispatcher = dispatcher
        self.context_builder = context_builder or ContextBuilder()
        self.completion_validator = completion_validator or CompletionValidator()
        self.repair_service = repair_service or RepairService()
        self.regeneration_service = regeneration_service or RegenerationService()
        self.missing_work_service = missing_work_service or MissingWorkService()
        self.progress_tracker = progress_tracker or WorkloadProgressTracker()

    def receive_workload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.plan_workload(request)

    def plan_workload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.planner.plan(request)

    def resolve_dependencies(self, resolver: Callable[[], Any]) -> Any:
        return resolver()

    def dispatch_handler(self, workload_type: str, category: str = "*") -> Any:
        return self.dispatcher.dispatch(workload_type, category)

    @staticmethod
    def collect_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return results

    @staticmethod
    def validate_results(validator: Any, objects: list[dict[str, Any]]) -> Any:
        return validator.validate(objects)

    def evaluate_progress(self, workload: dict[str, Any], packages: list[dict[str, Any]]) -> dict[str, Any]:
        return self.progress_tracker.calculate(workload, packages)

    def detect_missing_work(self, packages: list[dict[str, Any]]) -> list[Any]:
        return self.missing_work_service.detect(packages)

    def trigger_repair(self, objects: list[dict[str, Any]], context: dict[str, Any]) -> Any:
        return self.repair_service.repair(objects, context)

    def trigger_regeneration(self, missing: Any, generator: Any, workload: dict[str, Any], package: dict[str, Any], context: dict[str, Any]) -> Any:
        return self.regeneration_service.regenerate(missing, generator, workload, package, context)

    def evaluate_completion(self, workload: dict[str, Any], packages: list[dict[str, Any]], objects: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> dict[str, Any]:
        return self.completion_validator.evaluate(workload, packages, objects, dependencies)

    @staticmethod
    def submit_for_review(submitter: Callable[[dict[str, Any]], Any], payload: dict[str, Any]) -> Any:
        return submitter(payload)
