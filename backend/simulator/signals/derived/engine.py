from __future__ import annotations

from typing import Any

from .dependency_graph import SignalDependencyCycleError, SignalDependencyGraph


class DerivedSignalEngine:
    """Resolve dependency order for route-local signal evaluation."""

    def order(self, definitions: list[Any]) -> list[Any]:
        return SignalDependencyGraph(definitions).topological_order()

    def dirty_dependents(self, definitions: list[Any], signal_id: str) -> set[str]:
        return SignalDependencyGraph(definitions).dirty_dependents(signal_id)
