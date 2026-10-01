from __future__ import annotations

from typing import Any, Callable

from ..states import boolean_value, counter_value, event_impulse
from .actuator import actuator_status
from .camera import camera_status
from .controller import controller_status
from .function import function_status
from .gateway import gateway_status
from .motor import motor_status
from .network_interface import network_interface_status
from .sensor import sensor_status


StatusHandler = Callable[[Any, float, Any, Any], float]


class StatusModelRegistry:
    def __init__(self) -> None:
        self._handlers: list[tuple[tuple[str, ...], StatusHandler]] = [
            (("gateway", "gw"), gateway_status),
            (("camera", "kamera"), camera_status),
            (("sensor",), sensor_status),
            (("actuator", "aktor"), actuator_status),
            (("motor", "drive"), motor_status),
            (("function", "funktion"), function_status),
            (("interface", "network", "bus", "communication"), network_interface_status),
            (("ecu", "controller"), controller_status),
        ]

    def resolve(self, signal: Any) -> StatusHandler:
        haystack = f"{signal.name} {signal.domain} {signal.parameters.get('producer_type') or ''}".lower()
        for tokens, handler in self._handlers:
            if any(token in haystack for token in tokens):
                return handler
        return controller_status

    def generate(self, signal: Any, time_s: float, context: Any, state: Any) -> float:
        name = str(signal.name).lower()
        if "counter" in name or "alive" in name:
            modulus = max(1, int(signal.parameters.get("modulus") or 2 ** min(signal.length_bits, 16)))
            increment = int(signal.parameters.get("increment") or 1)
            return counter_value(time_s, signal.cycle_ms, modulus=modulus, increment=increment)
        if "event" in name:
            return event_impulse(time_s, at_s=float(signal.parameters.get("at_s") or 0.0), width_s=float(signal.parameters.get("width_s") or signal.cycle_ms / 1000.0))
        if "enabled" in name or "valid" in name or signal.length_bits == 1:
            return boolean_value(time_s, active_after_s=float(signal.parameters.get("active_after_s") or 1.5))
        return self.resolve(signal)(signal, time_s, context, state)
