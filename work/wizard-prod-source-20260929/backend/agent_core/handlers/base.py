from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseWorkloadHandler(ABC):
    """Domain workflow contract; concrete object creation stays in generators."""

    workload_type: str

    @abstractmethod
    def plan(self, orchestrator: Any, workload: dict[str, Any], packages: list[dict[str, Any]]) -> None: ...

    def inspect_existing_objects(self, orchestrator: Any, workload: dict[str, Any]) -> list[dict[str, Any]]:
        return orchestrator.list_workload_objects(str(workload["workload_id"]))

    def select_generator(self, orchestrator: Any, package: dict[str, Any]) -> Any:
        return orchestrator.generator_registry.get(self.workload_type, str(package.get("category") or "*"))

    @abstractmethod
    def execute(self, orchestrator: Any, workload: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def validate(self, orchestrator: Any, workload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def repair(self, orchestrator: Any, workload: dict[str, Any]) -> dict[str, Any]: ...

    def regenerate_missing(self, orchestrator: Any, workload: dict[str, Any]) -> dict[str, Any]:
        return orchestrator.generate_missing(str(workload["workload_id"]))

    def get_progress(self, orchestrator: Any, workload: dict[str, Any]) -> dict[str, Any]:
        return orchestrator.progress(str(workload["workload_id"]))

    def is_complete(self, orchestrator: Any, workload: dict[str, Any]) -> bool:
        return self.get_progress(orchestrator, workload)["status"] == "COMPLETED"
