from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RAGContext:
    approved_objects: list[dict[str, Any]] = field(default_factory=list)
    historical_solutions: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)
    imported_data: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved_objects": self.approved_objects,
            "historical_solutions": self.historical_solutions,
            "documents": self.documents,
            "imported_data": self.imported_data,
        }
