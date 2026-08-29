from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..errors import AgentCoreValidationError
from .workload_state import DependencyState, WorkloadStatus


@dataclass(frozen=True, slots=True)
class DependencyReadiness:
    state: DependencyState
    waiting_for: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()


class WorkloadDependencyGraph:
    """Directed graph where a node points to work it depends on."""

    def __init__(self) -> None:
        self._dependencies: dict[str, dict[str, str]] = {}
        self._mandatory_children: dict[str, set[str]] = {}

    def add_workload(self, workload_id: str) -> None:
        self._dependencies.setdefault(workload_id, {})

    def add_dependency(self, workload_id: str, dependency_id: str, required_status: str = "COMPLETED") -> None:
        if workload_id == dependency_id:
            raise AgentCoreValidationError("A workload cannot depend on itself.")
        self.add_workload(workload_id)
        self.add_workload(dependency_id)
        previous = self._dependencies[workload_id].get(dependency_id)
        self._dependencies[workload_id][dependency_id] = required_status.upper()
        try:
            self.execution_order()
        except AgentCoreValidationError:
            if previous is None:
                self._dependencies[workload_id].pop(dependency_id, None)
            else:
                self._dependencies[workload_id][dependency_id] = previous
            raise

    def add_child(self, parent_id: str, child_id: str, *, mandatory: bool = True) -> None:
        self.add_workload(parent_id)
        self.add_workload(child_id)
        if mandatory:
            self._mandatory_children.setdefault(parent_id, set()).add(child_id)
            self.add_dependency(parent_id, child_id, "COMPLETED")

    def dependencies_for(self, workload_id: str) -> dict[str, str]:
        return dict(self._dependencies.get(workload_id, {}))

    @staticmethod
    def _satisfied(actual: str | None, required: str) -> bool:
        if actual == required:
            return True
        return required == "READY_FOR_REVIEW" and actual == "COMPLETED"

    def readiness(self, workload_id: str, statuses: Mapping[str, str]) -> DependencyReadiness:
        waiting: list[str] = []
        blocked: list[str] = []
        blocking_statuses = {"BLOCKED", "FAILED", "CANCELED", "INCOMPLETE"}
        for dependency_id, required in self._dependencies.get(workload_id, {}).items():
            actual = str(statuses.get(dependency_id) or "RECEIVED").upper()
            if self._satisfied(actual, required):
                continue
            (blocked if actual in blocking_statuses else waiting).append(dependency_id)
        if blocked:
            return DependencyReadiness(DependencyState.BLOCKED, tuple(waiting), tuple(blocked))
        if waiting:
            return DependencyReadiness(DependencyState.WAITING, tuple(waiting), ())
        return DependencyReadiness(DependencyState.READY)

    def parent_complete(self, parent_id: str, statuses: Mapping[str, str]) -> bool:
        return all(str(statuses.get(child_id)) == WorkloadStatus.COMPLETED for child_id in self._mandatory_children.get(parent_id, set()))

    def execution_order(self) -> list[str]:
        visited: set[str] = set()
        visiting: set[str] = set()
        result: list[str] = []

        def visit(node: str) -> None:
            if node in visiting:
                raise AgentCoreValidationError("Workload dependency cycle detected.")
            if node in visited:
                return
            visiting.add(node)
            for dependency in self._dependencies.get(node, {}):
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
            result.append(node)

        for workload_id in self._dependencies:
            visit(workload_id)
        return result
