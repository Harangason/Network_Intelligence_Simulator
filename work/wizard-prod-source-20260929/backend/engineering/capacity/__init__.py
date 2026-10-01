"""Capacity and timing analysis services."""

__all__ = ["CapacityTimingService", "PreflightService"]


def __getattr__(name: str):
    if name in __all__:
        from .service import CapacityTimingService, PreflightService

        return {"CapacityTimingService": CapacityTimingService, "PreflightService": PreflightService}[name]
    raise AttributeError(name)
