"""Database, repositories, jobs, storage and runtime configuration."""

from ..models import Capability

CAPABILITY = Capability(
    "infrastructure", "Infrastructure",
    (
        "backend.engineering.db", "backend.engineering.repository",
        "backend.app.job_service", "backend.app.trace_storage",
        "backend.app.runtime_config", "backend.app.config",
    ),
    "Persistence and operating-system concerns kept outside domain decisions.",
)
__all__ = ["CAPABILITY"]
