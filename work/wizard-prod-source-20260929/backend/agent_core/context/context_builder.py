from __future__ import annotations

from typing import Any, Callable

from ..core.workload_context import WorkloadContext

ContextProvider = Callable[[dict[str, Any], dict[str, Any] | None], Any]


class ContextBuilder:
    """Adapter boundary: the Core receives context without knowing RAG or graph implementations."""

    def __init__(
        self,
        engineering_provider: ContextProvider | None = None,
        rag_provider: ContextProvider | None = None,
        graph_provider: ContextProvider | None = None,
    ) -> None:
        self.engineering_provider = engineering_provider
        self.rag_provider = rag_provider
        self.graph_provider = graph_provider

    @staticmethod
    def _value(provider: ContextProvider | None, workload: dict[str, Any], package: dict[str, Any] | None) -> dict[str, Any]:
        if provider is None:
            return {}
        value = provider(workload, package)
        if hasattr(value, "as_dict"):
            value = value.as_dict()
        return dict(value or {})

    def build(self, workload: dict[str, Any], package: dict[str, Any] | None = None) -> WorkloadContext:
        return WorkloadContext(
            engineering=self._value(self.engineering_provider, workload, package),
            rag=self._value(self.rag_provider, workload, package),
            graph=self._value(self.graph_provider, workload, package),
            execution={
                "workload_id": str(workload.get("workload_id") or ""),
                "work_package_id": str((package or {}).get("work_package_id") or ""),
            },
        )
