from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..registry import GeneratorRegistry, HandlerRegistry, ValidatorRegistry


@dataclass(frozen=True, slots=True)
class DispatchSelection:
    handler: Any
    generator: Any
    validators: tuple[Any, ...]


class WorkloadDispatcher:
    def __init__(
        self,
        handler_registry: HandlerRegistry,
        generator_registry: GeneratorRegistry,
        validator_registry: ValidatorRegistry,
    ) -> None:
        self.handlers = handler_registry
        self.generators = generator_registry
        self.validators = validator_registry

    def dispatch(self, workload_type: str, category: str = "*") -> DispatchSelection:
        return DispatchSelection(
            handler=self.handlers.get(workload_type),
            generator=self.generators.get(workload_type, category),
            validators=self.validators.for_type(workload_type),
        )
