"""Technology bindings, generators and capability registry."""

from .catalog import MODEL_TYPES, technology_definitions
from .core.registry import BindingResolver, GeneratorResolver, TechnologyRegistry


DEFAULT_TECHNOLOGY_REGISTRY = TechnologyRegistry()
DEFAULT_TECHNOLOGY_REGISTRY.register_defaults(technology_definitions())

__all__ = [
    "BindingResolver",
    "DEFAULT_TECHNOLOGY_REGISTRY",
    "GeneratorResolver",
    "MODEL_TYPES",
    "TechnologyRegistry",
]
