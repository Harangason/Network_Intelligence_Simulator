"""Agent Core exceptions independent of a concrete engineering domain."""


class AgentCoreError(RuntimeError):
    """Base error raised by the reusable Agent Core."""


class AgentCoreValidationError(AgentCoreError, ValueError):
    """Structured workload configuration or result is invalid."""


class RegistryLookupError(AgentCoreError, LookupError):
    """A required extension was not registered."""
