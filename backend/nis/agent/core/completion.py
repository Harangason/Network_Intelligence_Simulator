from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CompletionCriterion:
    metric: str
    operator: str
    value: Any


@dataclass(slots=True)
class CompletionDecision:
    status: str
    ready_for_review: bool
    complete: bool
    requested_count: int
    generated_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    missing_count: int
    checks: dict[str, bool] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready_for_review": self.ready_for_review,
            "complete": self.complete,
            "requested_count": self.requested_count,
            "generated_count": self.generated_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "duplicate_count": self.duplicate_count,
            "missing_count": self.missing_count,
            "checks": self.checks,
            "metrics": self.metrics,
            "reasons": self.reasons,
            "technical_success": self.generated_count > 0,
            "task_complete": self.complete,
        }
