from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SignalDependencyCycleError(ValueError):
    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__("Cyclic signal dependency: " + " -> ".join(cycle))


@dataclass
class SignalDependencyGraph:
    definitions: list[Any]

    def __post_init__(self) -> None:
        self.by_ref: dict[str, Any] = {}
        for definition in self.definitions:
            for ref in (
                str(definition.id),
                str(definition.name),
                str(definition.id).replace("-", "_"),
                str(definition.name).replace("-", "_"),
            ):
                self.by_ref[ref] = definition
        self.dependents: dict[str, set[str]] = {str(definition.id): set() for definition in self.definitions}
        for definition in self.definitions:
            for dependency_ref in getattr(definition, "dependencies", []):
                dependency = self.lookup(str(dependency_ref))
                if dependency is not None:
                    self.dependents.setdefault(str(dependency.id), set()).add(str(definition.id))

    def lookup(self, dependency_ref: str) -> Any | None:
        return self.by_ref.get(dependency_ref) or self.by_ref.get(dependency_ref.replace("-", "_"))

    def topological_order(self) -> list[Any]:
        visiting: list[str] = []
        visited: set[str] = set()
        ordered: list[Any] = []

        def visit(definition: Any) -> None:
            key = str(definition.id)
            if key in visited:
                return
            if key in visiting:
                raise SignalDependencyCycleError([*visiting[visiting.index(key):], key])
            visiting.append(key)
            for dependency_ref in getattr(definition, "dependencies", []):
                dependency = self.lookup(str(dependency_ref))
                if dependency is not None:
                    visit(dependency)
            visiting.pop()
            visited.add(key)
            ordered.append(definition)

        for definition in self.definitions:
            visit(definition)
        return ordered

    def dirty_dependents(self, signal_id: str) -> set[str]:
        dirty: set[str] = set()
        stack = list(self.dependents.get(signal_id, set()))
        while stack:
            item = stack.pop()
            if item in dirty:
                continue
            dirty.add(item)
            stack.extend(self.dependents.get(item, set()))
        return dirty
