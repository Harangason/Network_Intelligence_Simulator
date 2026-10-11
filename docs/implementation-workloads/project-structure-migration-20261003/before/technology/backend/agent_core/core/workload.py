from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..errors import AgentCoreValidationError
from .work_package import WorkPackage
from .workload_state import WorkloadStatus


@dataclass(slots=True)
class EngineeringWorkload:
    workload_id: str
    workload_type: str
    title: str
    target_total: int
    work_packages: list[WorkPackage]
    status: WorkloadStatus = WorkloadStatus.RECEIVED
    dependencies: list[str] = field(default_factory=list)
    completion_criteria: list[dict[str, Any]] = field(default_factory=list)
    parent_workload_id: str | None = None
    child_workload_ids: list[str] = field(default_factory=list)
    mandatory_child_ids: list[str] = field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.target_total <= 0:
            raise AgentCoreValidationError("Workloads require a positive target_total.")
        package_total = sum(package.requested_count for package in self.work_packages)
        if package_total != self.target_total:
            raise AgentCoreValidationError(
                f"WORKLOAD_CONFIGURATION_ERROR: package targets total {package_total}, expected {self.target_total}."
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EngineeringWorkload":
        packages = [WorkPackage.from_mapping(item) for item in value.get("work_packages") or []]
        return cls(
            workload_id=str(value.get("workload_id") or ""),
            workload_type=str(value.get("workload_type") or ""),
            title=str(value.get("title") or "Engineering Workload"),
            target_total=int(value.get("requested_total") or value.get("target_total") or 0),
            work_packages=packages,
            status=WorkloadStatus(str(value.get("status") or "RECEIVED")),
            dependencies=[str(item) for item in value.get("dependencies") or [] if not isinstance(item, dict)],
            completion_criteria=list(value.get("completion_criteria") or []),
            parent_workload_id=value.get("parent_workload_id"),
            child_workload_ids=[str(item) for item in value.get("child_workload_ids") or []],
            mandatory_child_ids=[str(item) for item in value.get("mandatory_child_ids") or []],
            attempts=int(value.get("attempts") or 0),
            max_attempts=int(value.get("max_generation_attempts") or value.get("max_attempts") or 3),
            metadata=dict(value.get("metadata") or {}),
        )

    def mandatory_children_complete(self, child_statuses: Mapping[str, str]) -> bool:
        return all(str(child_statuses.get(child_id)) == WorkloadStatus.COMPLETED for child_id in self.mandatory_child_ids)
