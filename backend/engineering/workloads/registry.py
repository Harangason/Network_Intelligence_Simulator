"""Compatibility adapter from engineering handlers to Agent Core registries."""

from __future__ import annotations

try:
    from backend.agent_core.errors import RegistryLookupError
    from backend.agent_core.handlers import BaseWorkloadHandler
    from backend.agent_core.registry import HandlerRegistry
except ModuleNotFoundError:  # Tests execute with backend as the import root.
    from agent_core.errors import RegistryLookupError
    from agent_core.handlers import BaseWorkloadHandler
    from agent_core.registry import HandlerRegistry

from ..models import EngineeringValidationError


class WorkloadHandler(BaseWorkloadHandler):
    """Domain handler contract retained for existing imports."""


class WorkloadTypeRegistry(HandlerRegistry):
    """Legacy name backed by the generic HandlerRegistry."""

    def register(self, handler: WorkloadHandler, workload_type: str | None = None, *, replace: bool = False) -> None:
        super().register(handler, workload_type, replace=replace)

    def get(self, workload_type: str) -> WorkloadHandler:
        try:
            return super().get(workload_type)
        except RegistryLookupError as error:
            raise EngineeringValidationError(f"Kein Workload-Handler fuer {workload_type!r} registriert.") from error
