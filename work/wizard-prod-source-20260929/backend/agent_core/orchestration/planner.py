from __future__ import annotations

from typing import Any, Callable, Mapping

from ..errors import AgentCoreValidationError


class WorkloadPlanner:
    """Turns a request into measurable packages through an injected parser."""

    def __init__(self, plan_factory: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self.plan_factory = plan_factory

    def plan(self, request: Mapping[str, Any] | str) -> dict[str, Any]:
        payload = dict(request) if isinstance(request, Mapping) else {"prompt": request}
        prompt = str(payload.get("prompt") or "").strip()
        if self.plan_factory:
            return self.plan_factory(prompt, payload)
        packages = list(payload.get("work_packages") or [])
        requested = int(payload.get("requested_total") or sum(int(item.get("requested_count") or 0) for item in packages))
        if requested <= 0 or not packages:
            raise AgentCoreValidationError("A structured request needs work_packages and a positive target.")
        if sum(int(item.get("requested_count") or 0) for item in packages) != requested:
            raise AgentCoreValidationError("WORKLOAD_CONFIGURATION_ERROR: package targets do not match total.")
        return {**payload, "requested_total": requested, "execution_order": [item.get("package_code") for item in packages]}
