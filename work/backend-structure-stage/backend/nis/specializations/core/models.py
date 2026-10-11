"""Small, behaviour-free source manifests for specialized NIS modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndustrySpecialization:
    """Locate industry vocabulary, templates and generation knowledge."""

    id: str
    label: str
    source_modules: tuple[str, ...]


@dataclass(frozen=True)
class TechnologySpecialization:
    """Locate technology profiles and specialized transport behaviour."""

    id: str
    technology_ids: tuple[str, ...]
    source_modules: tuple[str, ...]
