from __future__ import annotations

from typing import Any

from ..errors import AgentCoreValidationError, RegistryLookupError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, name: str, tool: Any, *, replace: bool = False) -> None:
        key = name.strip().lower()
        if not key:
            raise AgentCoreValidationError("Tools require a name.")
        if key in self._tools and not replace:
            raise AgentCoreValidationError(f"Tool {key!r} is already registered.")
        self._tools[key] = tool

    def get(self, name: str) -> Any:
        key = name.strip().lower()
        try:
            return self._tools[key]
        except KeyError as error:
            raise RegistryLookupError(f"No tool {key!r} is registered.") from error
