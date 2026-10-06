"""Public contracts for the generic communication core."""

from backend.nis.communication.core.models import FunctionalInterface, HardwareInterface, HardwareNode, Layer, PayloadElement, TechnologyBinding, TechnologyCapability, TechnologyStack, TransportRequirement, TransportUnit


__all__ = [
    "BindingResolver",
    "FunctionalInterface",
    "GeneratorResolver",
    "HardwareInterface",
    "HardwareNode",
    "Layer",
    "PayloadElement",
    "TechnologyBinding",
    "TechnologyCapability",
    "TechnologyRegistry",
    "TechnologyStack",
    "TransportRequirement",
    "TransportUnit",
]

def __getattr__(name):
    if name in ("BindingResolver", "GeneratorResolver", "TechnologyRegistry"):
        from backend.nis.communication import registry
        return getattr(registry, name)
    raise AttributeError(name)
