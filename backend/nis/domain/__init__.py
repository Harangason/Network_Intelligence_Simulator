"""Canonical engineering concepts shared by all workflow stages."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "domain", "Engineering domain",
    (
        "backend.nis.domain.core", "backend.nis.domain.vocabulary",
        "backend.nis.engineering.routing", "backend.nis.engineering.relations",
        "backend.nis.engineering.signals.message_bindings", "backend.nis.engineering.scope_rules",
    ),
    "Canonical model, communication intent, routing semantics and relations.",
)
__all__ = ["CAPABILITY"]
