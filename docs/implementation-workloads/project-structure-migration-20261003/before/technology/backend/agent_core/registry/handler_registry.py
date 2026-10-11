from __future__ import annotations

from typing import Any

from ..errors import AgentCoreValidationError, RegistryLookupError


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    def register(self, handler: Any, workload_type: str | None = None, *, replace: bool = False) -> None:
        key = str(workload_type or getattr(handler, "workload_type", "")).strip().upper()
        if not key:
            raise AgentCoreValidationError("Handlers require a workload_type.")
        if key in self._handlers and not replace:
            raise AgentCoreValidationError(f"Handler for {key!r} is already registered.")
        self._handlers[key] = handler

    def get(self, workload_type: str) -> Any:
        key = workload_type.strip().upper()
        try:
            return self._handlers[key]
        except KeyError as error:
            raise RegistryLookupError(f"No workload handler for {key!r} is registered.") from error

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))
