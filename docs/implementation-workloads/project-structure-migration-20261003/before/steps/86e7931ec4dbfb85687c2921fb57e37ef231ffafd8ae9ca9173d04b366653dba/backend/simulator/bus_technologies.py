"""Compatibility facade for the class-based industry technology registry.

New code may import :class:`physic_lib.Industries.TechnologyRegistry` directly.
The functions below intentionally preserve the original public API.
"""

from __future__ import annotations

from typing import Any, Iterable

from physic_lib.Industries.registry import ALIASES, TechnologyRegistry


DEFAULT_TECHNOLOGY_REGISTRY = TechnologyRegistry()
BUILTIN_TECHNOLOGIES = DEFAULT_TECHNOLOGY_REGISTRY.builtin


def normalize_technology_id(value: Any) -> str:
    return DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(value)


def technology_registry(
    custom_profiles: Iterable[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    return DEFAULT_TECHNOLOGY_REGISTRY.build(custom_profiles)


def resolve_technology(
    value: Any,
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return DEFAULT_TECHNOLOGY_REGISTRY.resolve(value, registry)


def catalog_summary(
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return DEFAULT_TECHNOLOGY_REGISTRY.summary(registry)


__all__ = [
    "ALIASES",
    "BUILTIN_TECHNOLOGIES",
    "DEFAULT_TECHNOLOGY_REGISTRY",
    "TechnologyRegistry",
    "catalog_summary",
    "normalize_technology_id",
    "resolve_technology",
    "technology_registry",
]
