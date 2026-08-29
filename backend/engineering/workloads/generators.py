"""Simulator-specific generators plugged into the generic Agent Core registry."""

from __future__ import annotations

from typing import Any

try:
    from backend.agent_core.generators import BaseGenerator, GeneratorResult
except ModuleNotFoundError:  # Tests execute with backend as the import root.
    from agent_core.generators import BaseGenerator, GeneratorResult

from .handlers import (
    MOTION_SIGNAL_CATALOG,
    THERMAL_SIGNAL_CATALOG,
    _existing_signal_definition,
    _signal_definition,
    normalized_name,
)


class CatalogSignalGenerator(BaseGenerator):
    workload_type = "SIGNAL_GENERATION"

    def __init__(self, category: str, catalog: tuple[dict[str, Any], ...]) -> None:
        self.category = category
        self.catalog = catalog

    def generate(
        self,
        requested: int,
        *,
        workload: dict[str, Any],
        package: dict[str, Any],
        context: dict[str, Any],
        existing: list[dict[str, Any]],
    ) -> GeneratorResult:
        candidates = self.catalog[:requested]
        existing_by_name = {normalized_name(item.get("name")): item for item in existing}
        package_objects = list(context.get("workload_objects") or [])
        existing_keys = {str(item["object_key"]) for item in package_objects}
        generated: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            key = f"signal:{self.category}:{normalized_name(candidate['name'])}"
            if key in existing_keys:
                continue
            canonical = existing_by_name.get(normalized_name(candidate["name"]))
            if canonical:
                definition = _existing_signal_definition(workload, package, candidate, canonical, context)
                generated.append(
                    {
                        "object_key": key,
                        "definition": definition,
                        "canonical_id": str(canonical["id"]),
                        "approval_state": str(canonical.get("approval_state") or "approved").upper(),
                        "review_state": str(canonical.get("review_state") or "reviewed").upper(),
                    }
                )
            else:
                generated.append(
                    {
                        "object_key": key,
                        "definition": _signal_definition(workload, package, candidate, context, index),
                    }
                )
        total_after = len(package_objects) + len(generated)
        return GeneratorResult(
            status="SUCCESS",
            requested=requested,
            generated=len(generated),
            remaining=max(0, requested - total_after),
            objects=generated,
        )


class TemperatureSignalGenerator(CatalogSignalGenerator):
    def __init__(self) -> None:
        super().__init__("thermal", THERMAL_SIGNAL_CATALOG)


class MotionSignalGenerator(CatalogSignalGenerator):
    def __init__(self) -> None:
        super().__init__("motion", MOTION_SIGNAL_CATALOG)


class GenericSignalGenerator(CatalogSignalGenerator):
    def __init__(self, category: str, catalog: tuple[dict[str, Any], ...]) -> None:
        super().__init__(category, catalog)


def default_signal_generators() -> tuple[BaseGenerator, ...]:
    return (TemperatureSignalGenerator(), MotionSignalGenerator())
