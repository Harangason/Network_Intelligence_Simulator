"""Technology bindings, generators, capability registry and knowledge onboarding."""

import os

from backend.nis.communication.catalog import MODEL_TYPES, technology_definitions
from backend.nis.communication.registry import BindingResolver, GeneratorResolver, TechnologyRegistry, format_rate_bps
from backend.nis.communication.services.onboarding import TechnologyOnboardingService


DEFAULT_TECHNOLOGY_REGISTRY = TechnologyRegistry()
DEFAULT_TECHNOLOGY_REGISTRY.register_defaults(technology_definitions())
DEFAULT_TECHNOLOGY_ONBOARDING = TechnologyOnboardingService(DEFAULT_TECHNOLOGY_REGISTRY)
if os.environ.get("NIS_DISABLE_GENERATED_TECHNOLOGIES", "").lower() not in {"1", "true", "yes"}:
    DEFAULT_TECHNOLOGY_ONBOARDING.load_registered_packs()

__all__ = [
    "BindingResolver",
    "DEFAULT_TECHNOLOGY_REGISTRY",
    "DEFAULT_TECHNOLOGY_ONBOARDING",
    "GeneratorResolver",
    "MODEL_TYPES",
    "TechnologyRegistry",
    "TechnologyOnboardingService",
    "format_rate_bps",
]


def __getattr__(name):
    """Legacy public child names resolve to the one canonical owner."""
    import importlib
    from backend.nis.compatibility import ALIASES
    target = ALIASES.get('backend.communication.technologies.' + name)
    if target is not None:
        return importlib.import_module(target)
    raise AttributeError(name)
