"""Database, repositories, jobs, storage and runtime configuration."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "infrastructure", "Infrastructure",
    (
        "backend.nis.infrastructure.persistence.db", "backend.nis.infrastructure.persistence.repository",
        "backend.nis.simulation.job_service", "backend.nis.infrastructure.storage.trace_storage",
        "backend.nis.app.runtime_config", "backend.nis.infrastructure.paths",
    ),
    "Persistence and operating-system concerns kept outside domain decisions.",
)
__all__ = ["CAPABILITY"]
