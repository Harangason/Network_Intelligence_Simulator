from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..errors import AgentCoreValidationError


@dataclass(slots=True)
class GeneratorResult:
    status: str
    requested: int
    generated: int
    valid: int = 0
    invalid: int = 0
    remaining: int = 0
    objects: list[Any] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if min(self.requested, self.generated, self.valid, self.invalid, self.remaining) < 0:
            raise AgentCoreValidationError("Generator counts cannot be negative.")
        if self.valid + self.invalid > self.generated:
            raise AgentCoreValidationError("Generator valid/invalid counts exceed generated count.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "requested": self.requested,
            "generated": self.generated,
            "valid": self.valid,
            "invalid": self.invalid,
            "remaining": self.remaining,
            "objects": self.objects,
            "findings": self.findings,
            "validation_findings": self.findings,
        }


class BaseGenerator(ABC):
    workload_type: str
    category: str = "*"

    @abstractmethod
    def generate(
        self,
        requested: int,
        *,
        workload: dict[str, Any],
        package: dict[str, Any],
        context: dict[str, Any],
        existing: list[dict[str, Any]],
    ) -> GeneratorResult: ...
