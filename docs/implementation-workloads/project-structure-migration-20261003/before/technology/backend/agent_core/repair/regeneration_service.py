from __future__ import annotations

from typing import Any

from .missing_work_service import MissingWork


class RegenerationService:
    def regenerate(
        self,
        missing: MissingWork,
        generator: Any,
        workload: dict[str, Any],
        package: dict[str, Any],
        context: dict[str, Any],
        existing: list[dict[str, Any]] | None = None,
    ) -> Any:
        return generator.generate(
            missing.count,
            workload=workload,
            package=package,
            context=context,
            existing=existing or [],
        )
