from __future__ import annotations

from typing import Any, Callable


class RepairService:
    def __init__(self) -> None:
        self._strategies: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]] = {}

    def register(self, finding_code: str, strategy: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]) -> None:
        self._strategies[finding_code.strip().upper()] = strategy

    def repair(self, objects: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        repaired: list[dict[str, Any]] = []
        needs_review: list[str] = []
        for item in objects:
            updated = dict(item)
            changed = False
            for finding in item.get("validation_results") or []:
                code = str(finding.get("code") or "").upper()
                strategy = self._strategies.get(code)
                if strategy is None:
                    needs_review.append(str(item.get("id") or item.get("workload_object_id") or "unknown"))
                    continue
                candidate = strategy(updated, context)
                if candidate is not None:
                    updated = candidate
                    changed = True
            if changed:
                repaired.append(updated)
        return {
            "status": "SUCCESS" if repaired else "NEEDS_REVIEW",
            "repaired": repaired,
            "repaired_count": len(repaired),
            "needs_review": sorted(set(needs_review)),
        }
