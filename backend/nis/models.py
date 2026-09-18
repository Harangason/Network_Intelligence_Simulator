"""Architecture metadata without runtime coupling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """Locate one high-level NIS responsibility in the existing codebase."""

    id: str
    label: str
    source_modules: tuple[str, ...]
    responsibility: str
