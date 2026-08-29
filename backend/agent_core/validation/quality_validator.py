from __future__ import annotations

from typing import Any, Iterable, Mapping


class QualityValidator:
    def __init__(self, required_fields: Iterable[str] = ()) -> None:
        self.required_fields = tuple(required_fields)

    def validate(self, definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {"code": "MISSING_FIELD", "field": field, "severity": "ERROR"}
            for field in self.required_fields
            if definition.get(field) is None or definition.get(field) == ""
        ]
