from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..errors import AgentCoreValidationError
from .workload_state import WorkloadStatus


@dataclass(slots=True)
class WorkPackage:
    package_code: str
    category: str
    target_object: str
    requested_count: int
    generated_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    duplicate_count: int = 0
    attempts: int = 0
    max_attempts: int = 3
    status: WorkloadStatus = WorkloadStatus.RECEIVED
    configuration: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.requested_count <= 0:
            raise AgentCoreValidationError("Work Packages require a positive target.")
        if self.max_attempts <= 0:
            raise AgentCoreValidationError("max_attempts must be positive.")

    @property
    def missing_count(self) -> int:
        return max(0, self.requested_count - self.valid_count)

    @property
    def progress_percent(self) -> float:
        return round(min(self.valid_count, self.requested_count) * 100 / self.requested_count, 2)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkPackage":
        return cls(
            package_code=str(value.get("package_code") or value.get("work_package_id") or "WP"),
            category=str(value.get("category") or "general"),
            target_object=str(value.get("target_object") or "Object"),
            requested_count=int(value.get("requested_count") or 0),
            generated_count=int(value.get("generated_count") or 0),
            valid_count=int(value.get("valid_count") or 0),
            invalid_count=int(value.get("invalid_count") or 0),
            duplicate_count=int(value.get("duplicate_count") or 0),
            attempts=int(value.get("attempts") or 0),
            max_attempts=int(value.get("max_generation_attempts") or value.get("max_attempts") or 3),
            status=WorkloadStatus(str(value.get("status") or "RECEIVED")),
            configuration=dict(value.get("configuration") or {}),
            findings=list(value.get("findings") or []),
        )
