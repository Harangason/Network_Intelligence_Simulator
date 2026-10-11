from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkloadContext:
    engineering: dict[str, Any] = field(default_factory=dict)
    rag: dict[str, Any] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "engineering": self.engineering,
            "rag": self.rag,
            "graph": self.graph,
            "execution": self.execution,
        }
