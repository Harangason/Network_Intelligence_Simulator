"""Technology bindings, generators, capability registry and knowledge onboarding."""

import os

from .catalog import MODEL_TYPES, technology_definitions
from .core.registry import BindingResolver, GeneratorResolver, TechnologyRegistry
from .onboarding import TechnologyOnboardingService


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
]
