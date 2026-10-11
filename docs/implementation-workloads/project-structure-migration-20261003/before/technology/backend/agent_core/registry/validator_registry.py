from __future__ import annotations

from typing import Any

from ..errors import AgentCoreValidationError, RegistryLookupError


class ValidatorRegistry:
    def __init__(self) -> None:
        self._validators: dict[tuple[str, str], Any] = {}

    def register(self, validator: Any, workload_type: str, name: str = "default", *, replace: bool = False) -> None:
        key = (workload_type.strip().upper(), name.strip().lower())
        if not key[0] or not key[1]:
            raise AgentCoreValidationError("Validators require workload_type and name.")
        if key in self._validators and not replace:
            raise AgentCoreValidationError(f"Validator {key!r} is already registered.")
        self._validators[key] = validator

    def get(self, workload_type: str, name: str = "default") -> Any:
        key = (workload_type.strip().upper(), name.strip().lower())
        try:
            return self._validators[key]
        except KeyError as error:
            raise RegistryLookupError(f"No validator {key!r} is registered.") from error

    def for_type(self, workload_type: str) -> tuple[Any, ...]:
        key = workload_type.strip().upper()
        return tuple(value for (registered_type, _), value in self._validators.items() if registered_type == key)
