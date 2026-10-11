from __future__ import annotations

from typing import Any

from ..errors import AgentCoreValidationError, RegistryLookupError


class GeneratorRegistry:
    def __init__(self) -> None:
        self._generators: dict[tuple[str, str], Any] = {}

    def register(
        self,
        generator: Any,
        workload_type: str | None = None,
        category: str | None = None,
        *,
        replace: bool = False,
    ) -> None:
        type_key = str(workload_type or getattr(generator, "workload_type", "")).strip().upper()
        category_key = str(category or getattr(generator, "category", "*")).strip().lower() or "*"
        if not type_key:
            raise AgentCoreValidationError("Generators require a workload_type.")
        key = (type_key, category_key)
        if key in self._generators and not replace:
            raise AgentCoreValidationError(f"Generator for {key!r} is already registered.")
        self._generators[key] = generator

    def get(self, workload_type: str, category: str | None = None) -> Any:
        type_key = workload_type.strip().upper()
        category_key = str(category or "*").strip().lower() or "*"
        generator = self._generators.get((type_key, category_key)) or self._generators.get((type_key, "*"))
        if generator is None:
            raise RegistryLookupError(f"No generator for {(type_key, category_key)!r} is registered.")
        return generator

    def keys(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._generators))
