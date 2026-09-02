from __future__ import annotations

from typing import Any, Callable

from .acceleration import acceleration
from .current import current
from .generic_physical import generic_physical
from .position import position
from .pressure import pressure
from .rotational_speed import rotational_speed
from .temperature import temperature
from .torque import torque
from .velocity import velocity
from .voltage import voltage


PhysicalHandler = Callable[[Any, float, Any, Any], float]


class PhysicalModelRegistry:
    def __init__(self) -> None:
        self._handlers: list[tuple[tuple[str, ...], PhysicalHandler]] = [
            (("temperature", "temp"), temperature),
            (("rpm", "rotational", "rotation", "speed"), rotational_speed),
            (("torque",), torque),
            (("pressure", "press"), pressure),
            (("voltage", "volt"), voltage),
            (("current", "amp"), current),
            (("position", "angle"), position),
            (("velocity",), velocity),
            (("acceleration", "accel"), acceleration),
        ]

    def resolve(self, signal: Any) -> PhysicalHandler:
        haystack = f"{signal.name} {signal.unit} {signal.parameters.get('semantic_type') or ''}".lower()
        for tokens, handler in self._handlers:
            if any(token in haystack for token in tokens):
                return handler
        return generic_physical

    def generate(self, signal: Any, time_s: float, context: Any, state: Any) -> float:
        return self.resolve(signal)(signal, time_s, context, state)
