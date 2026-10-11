"""Deterministic intelligence, analytics and machine learning."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "intelligence", "Data Science & Intelligence",
    ("backend.nis.intelligence.engineering.intelligence", "backend.nis.intelligence.engineering.semantic_intelligence", "backend.nis.intelligence"),
    "System assessment, semantic reasoning, analytics and ML models.",
)
__all__ = ["CAPABILITY"]
