"""Deterministic intelligence, analytics and machine learning."""

from ..models import Capability

CAPABILITY = Capability(
    "intelligence", "Data Science & Intelligence",
    ("backend.engineering.intelligence", "backend.engineering.semantic_intelligence", "backend.intelligence"),
    "System assessment, semantic reasoning, analytics and ML models.",
)
__all__ = ["CAPABILITY"]
