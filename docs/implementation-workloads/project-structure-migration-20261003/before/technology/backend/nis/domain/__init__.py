"""Canonical engineering concepts shared by all workflow stages."""

from ..models import Capability

CAPABILITY = Capability(
    "domain", "Engineering domain",
    (
        "backend.engineering.core", "backend.engineering.models",
        "backend.engineering.routing", "backend.engineering.relations",
        "backend.engineering.message_bindings", "backend.engineering.scope_rules",
    ),
    "Canonical model, communication intent, routing semantics and relations.",
)
__all__ = ["CAPABILITY"]
