from __future__ import annotations

from dataclasses import dataclass

from ..errors import AgentCoreValidationError, RegistryLookupError


@dataclass(frozen=True, slots=True)
class WorkloadTypeDefinition:
    workload_type: str
    target_object: str
    description: str = ""


class WorkloadTypeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, WorkloadTypeDefinition] = {}

    def register(self, definition: WorkloadTypeDefinition, *, replace: bool = False) -> None:
        key = definition.workload_type.strip().upper()
        if not key:
            raise AgentCoreValidationError("workload_type is required.")
        if key in self._definitions and not replace:
            raise AgentCoreValidationError(f"Workload type {key!r} is already registered.")
        self._definitions[key] = WorkloadTypeDefinition(key, definition.target_object, definition.description)

    def get(self, workload_type: str) -> WorkloadTypeDefinition:
        key = workload_type.strip().upper()
        try:
            return self._definitions[key]
        except KeyError as error:
            raise RegistryLookupError(f"No workload type {key!r} is registered.") from error

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))
