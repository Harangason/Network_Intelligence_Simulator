from __future__ import annotations

from typing import Any, Iterable, Mapping


class DependencyValidator:
    def validate(self, dependencies: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "code": "DEPENDENCY_NOT_SATISFIED",
                "severity": "ERROR",
                "dependency_workload_id": item.get("dependency_workload_id") or item.get("workload_id"),
                "status": item.get("status"),
                "required_status": item.get("required_status"),
            }
            for item in dependencies
            if not bool(item.get("satisfied"))
        ]
