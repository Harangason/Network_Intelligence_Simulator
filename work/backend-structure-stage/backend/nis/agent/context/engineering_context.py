from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EngineeringContext:
    project_id: str | None = None
    objects: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    requirements: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "objects": self.objects,
            "requirements": self.requirements,
            "validation_results": self.validation_results,
            **self.metadata,
        }
