from __future__ import annotations

from typing import Any

from ..constraints import SignalConstraintEngine
from ..encoding import SignalEncodingService
from ..noise import SignalNoiseEngine
from ..quality import SignalQualityEngine
from .context import SimulationContext
from .model_type import normalize_model_type
from .random_service import SimulationRandomService
from .registry import SignalBehaviorRegistry, clamp, number, stable_seed
from .runtime_state import SignalRuntimeState
from .sample import SignalSample


class SignalEmulator:
    def initialize(self, definition: Any, context: SimulationContext) -> None:
        raise NotImplementedError

    def step(self, definition: Any, time_s: float, dt: float, context: SimulationContext) -> SignalSample:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class PlausibleSignalEmulationService(SignalEmulator):
    def __init__(self, *, seed: int, registry: SignalBehaviorRegistry | None = None) -> None:
        self.seed = seed
        self.random = SimulationRandomService(seed)
        self.registry = registry or SignalBehaviorRegistry()
        self.state = SignalRuntimeState()
        self.constraints = SignalConstraintEngine()
        self.noise = SignalNoiseEngine(self.random)
        self.encoding = SignalEncodingService()
        self.quality = SignalQualityEngine()

    def initialize(self, definition: Any, _context: SimulationContext) -> None:
        if definition.id not in self.state.values:
            initial = number(definition.parameters.get("initial_value"), _initial_default(definition, _context))
            self.state.update(definition.id, 0.0, clamp(initial, definition.minimum, definition.maximum))

    def reset(self) -> None:
        self.state = SignalRuntimeState()

    def step(self, definition: Any, time_s: float, dt: float, context: SimulationContext) -> SignalSample:
        context.current_time = time_s
        context.dt = dt
        context.seed = self.seed
        self.initialize(definition, context)
        semantic_type = infer_semantic_type(definition)
        behavior_value = self.registry.generate(definition, time_s, context, self.state)
        constrained = self.constraints.apply(definition, behavior_value, time_s, self.state)
        noisy = constrained if semantic_type in {"ENUM", "STATE", "BOOLEAN", "COUNTER", "BITFIELD", "EVENT", "QUALITY"} else self.noise.apply(definition, constrained, time_s, context)
        quantized = self.encoding.quantize(definition, noisy)
        raw = self.encoding.raw_value(definition, quantized)
        quality = self.quality.evaluate(definition, quantized)
        self.state.update(definition.id, time_s, quantized)
        model_type = normalize_model_type(definition.model_label, behavior_type=definition.behavior_type, semantic_type=semantic_type)
        state_label = _state_label(definition, quantized, context) if semantic_type in {"ENUM", "STATE", "BOOLEAN", "COUNTER", "BITFIELD", "EVENT", "QUALITY"} else None
        return SignalSample(
            signal_ref=definition.id,
            timestamp=time_s,
            semantic_type=semantic_type,
            physical_value=noisy,
            display_value=state_label if state_label is not None else quantized,
            quantized_value=quantized,
            raw_value=raw,
            unit=definition.unit,
            quality=quality,
            model_type=model_type,
            behavior_model=definition.behavior_type,
            state=state_label,
            golden_value=constrained,
            source_dependencies=list(definition.dependencies),
            metadata={"semantic_type": semantic_type, "model_type": model_type, "behavior_model": definition.behavior_type},
        )

    def delayed(self, signal_id: str, time_s: float, delay_s: float, fallback: float) -> float:
        return self.state.delayed(signal_id, time_s, delay_s, fallback)

    def _apply_constraints(self, definition: Any, value: float, time_s: float) -> float:
        return self.constraints.apply(definition, value, time_s, self.state)

    @staticmethod
    def _apply_resolution(definition: Any, value: float) -> float:
        return SignalEncodingService.quantize(definition, value)

    def _apply_noise(self, definition: Any, value: float, time_s: float, context: SimulationContext) -> float:
        return self.noise.apply(definition, value, time_s, context)

    @staticmethod
    def _raw_value(definition: Any, value: float | None) -> int | None:
        return SignalEncodingService.raw_value(definition, value)

    @staticmethod
    def _quality(definition: Any, value: float | None) -> str:
        return SignalQualityEngine().evaluate(definition, value)


def infer_semantic_type(definition: Any) -> str:
    configured = str(definition.parameters.get("semantic_type") or definition.parameters.get("signal_type") or "").upper()
    if configured:
        return configured
    name = str(definition.name).lower()
    data_type = str(definition.data_type).lower()
    if definition.enum_values or "enum" in data_type:
        return "ENUM"
    if "state" in name or "status" in name:
        return "STATE"
    if "enabled" in name or "valid" in name or data_type in {"bool", "boolean"} or definition.length_bits == 1:
        return "BOOLEAN"
    if "counter" in name or "alive" in name:
        return "COUNTER"
    if "flag" in name or "bitfield" in data_type:
        return "BITFIELD"
    if "command" in name or "request" in name:
        return "COMMAND"
    if "event" in name:
        return "EVENT"
    if definition.dependencies or str(definition.behavior_type).upper() in {"FORMULA", "STATE_DEPENDENT"}:
        return "DERIVED"
    if "quality" in name:
        return "QUALITY"
    if data_type in {"raw", "bytes"}:
        return "RAW"
    return "NUMERIC_PHYSICAL"


def _state_label(definition: Any, value: float | None, context: SimulationContext) -> str | None:
    if value is None:
        return None
    enum = getattr(definition, "enum_values", {}) or {}
    rounded = int(round(value))
    for label, code in enum.items():
        if int(code) == rounded:
            return str(label)
    system_state = getattr(context, "system_state", {})
    if isinstance(system_state, dict):
        state_name = system_state.get("operating_state")
        if state_name and ("state" in str(definition.name).lower() or "status" in str(definition.name).lower()):
            return str(state_name)
    if "bool" in str(definition.data_type).lower() or getattr(definition, "length_bits", 0) == 1:
        return "TRUE" if rounded else "FALSE"
    return str(rounded)


def _initial_default(definition: Any, context: SimulationContext) -> float:
    name = str(definition.name).lower()
    semantic_type = infer_semantic_type(definition)
    if semantic_type in {"ENUM", "STATE", "BOOLEAN", "COUNTER", "BITFIELD", "EVENT", "QUALITY"}:
        return float(definition.minimum)
    if "temperature" in name or "temp" in name:
        return number(getattr(context, "environment", {}).get("ambient_temperature"), 22.0)
    if any(token in name for token in ("rpm", "speed", "torque", "current", "velocity", "acceleration")) and definition.minimum <= 0:
        return 0.0
    return (definition.minimum + definition.maximum) / 2.0
