"""Deterministic signal, behavior, codec, and fault simulation primitives."""

from __future__ import annotations

import ast
import hashlib
import math
import operator
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol


BEHAVIOR_TYPES = (
    "CONSTANT", "STEP", "RAMP", "LINEAR", "SINE", "TRIANGLE", "SAWTOOTH",
    "PULSE", "RANDOM_WALK", "BOUNDED_RANDOM", "STATE_DEPENDENT", "FORMULA",
    "LOOKUP_TABLE", "EXTERNAL_SERIES",
)
MODEL_LABELS = (
    "PHYSICS_BASED", "RULE_BASED", "EMPIRICAL", "SYNTHETIC", "GENERIC_ESTIMATE",
)
DEFAULT_MODEL_TRACE_FRAME_LIMIT = 10_000
DEFAULT_MODEL_TRACE_SIGNAL_POINT_LIMIT = 20_000
DEFAULT_MODEL_TRACE_EVENT_LIMIT = 5_000
SIGNAL_FAULTS = (
    "SIGNAL_STUCK", "SIGNAL_OFFSET", "SIGNAL_DRIFT", "SIGNAL_SPIKE", "SIGNAL_DROPOUT", "SIGNAL_NOISE",
    "SIGNAL_OUT_OF_RANGE", "SIGNAL_FROZEN", "SIGNAL_DELAYED", "SIGNAL_WRONG_SCALE", "SIGNAL_INVALID_VALUE",
)
MESSAGE_FAULTS = (
    "MESSAGE_LOSS", "MESSAGE_DELAY", "MESSAGE_JITTER", "MESSAGE_DUPLICATION", "MESSAGE_CORRUPTION", "MESSAGE_WRONG_CYCLE",
    "MESSAGE_TIMEOUT", "BURST_TRAFFIC", "FRAME_ERROR", "ROUTING_FAILURE",
)
NETWORK_FAULTS = (
    "NETWORK_OVERLOAD", "BUS_OFF", "LINK_DOWN", "GATEWAY_DELAY", "GATEWAY_DROP",
    "QUEUE_OVERFLOW", "CONGESTION", "TEMPORARY_DISCONNECT",
)

FAULT_ALIASES = {
    **{name.removeprefix("SIGNAL_"): name for name in SIGNAL_FAULTS},
    **{name.removeprefix("MESSAGE_"): name for name in MESSAGE_FAULTS if name.startswith("MESSAGE_")},
    "OVERLOAD": "NETWORK_OVERLOAD",
}


def normalize_fault_type(value: object) -> str:
    normalized = str(value or "").upper()
    return FAULT_ALIASES.get(normalized, normalized)


class BehaviorModel(Protocol):
    """Extension point for simple, formula, state-machine, external, or FMU adapters."""

    def generate(self, signal: "SignalDefinition", time_s: float, context: dict[str, float]) -> float: ...


def _number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _trace_limit(config: dict[str, Any], key: str, default: int) -> int:
    try:
        value = int(config.get(key) if config.get(key) is not None else default)
    except (TypeError, ValueError):
        return default
    return max(0, value)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _stable_seed(seed: int, *parts: object) -> int:
    digest = hashlib.sha256(":".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class FormulaEvaluator:
    """Evaluate arithmetic formulas without exposing Python execution."""

    _operators = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    _functions = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
        "abs": abs, "min": min, "max": max,
    }

    @classmethod
    def evaluate(cls, expression: str, variables: dict[str, float]) -> float:
        tree = ast.parse(expression, mode="eval")

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.Name) and node.id in variables:
                return float(variables[node.id])
            if isinstance(node, ast.BinOp) and type(node.op) in cls._operators:
                return float(cls._operators[type(node.op)](visit(node.left), visit(node.right)))
            if isinstance(node, ast.UnaryOp) and type(node.op) in cls._operators:
                return float(cls._operators[type(node.op)](visit(node.operand)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in cls._functions:
                return float(cls._functions[node.func.id](*(visit(argument) for argument in node.args)))
            raise ValueError("Unsupported formula expression")

        return visit(tree)


@dataclass(frozen=True)
class SignalDefinition:
    id: str
    name: str
    message_id: str
    minimum: float
    maximum: float
    unit: str
    resolution: float
    cycle_ms: float
    start_bit: int
    length_bits: int
    byte_order: str
    factor: float
    offset: float
    behavior_type: str
    model_label: str
    parameters: dict[str, Any]
    dependencies: list[str]
    domain: str
    data_type: str
    invalid_value: float | None
    enum_values: dict[str, int]

    @classmethod
    def from_record(cls, raw: dict[str, Any], message: dict[str, Any] | None = None) -> "SignalDefinition":
        configuration = _mapping(raw.get("configuration"))
        data = _mapping(raw.get("data"))
        communication = _mapping(raw.get("communication"))
        behavior = _mapping(raw.get("behavior")) or _mapping(configuration.get("behavior"))
        minimum = _number(raw.get("min_value"), _number(data.get("minimum"), 0.0))
        maximum = _number(raw.get("max_value"), _number(data.get("maximum"), minimum + 100.0))
        if maximum <= minimum:
            maximum = minimum + 1.0
        factor = max(1e-12, abs(_number(raw.get("factor"), _number(data.get("resolution"), 1.0))))
        behavior_type = str(behavior.get("behavior_type") or behavior.get("type") or "").upper()
        name = str(raw.get("name") or raw.get("display_name") or raw.get("id") or "Signal")
        if behavior_type not in BEHAVIOR_TYPES:
            lowered = f"{name} {raw.get('domain') or ''}".lower()
            behavior_type = "SINE" if "temper" in lowered else "RAMP" if "motion" in lowered else "BOUNDED_RANDOM"
        model_label = str(behavior.get("model_label") or "GENERIC_ESTIMATE").upper()
        if model_label not in MODEL_LABELS:
            model_label = "GENERIC_ESTIMATE"
        cycle_ms = _number(
            communication.get("cycle_ms"),
            _number((message or {}).get("cycle_ms"), 100.0),
        )
        dependencies = [str(item) for item in _sequence(behavior.get("dependencies") or raw.get("dependencies"))]
        return cls(
            id=str(raw.get("id") or name),
            name=name,
            message_id=str(raw.get("message_id") or ""),
            minimum=minimum,
            maximum=maximum,
            unit=str(raw.get("unit") or data.get("unit") or ""),
            resolution=factor,
            cycle_ms=max(0.001, cycle_ms),
            start_bit=max(0, int(raw.get("start_bit") or 0)),
            length_bits=max(1, int(raw.get("length_bits") or 16)),
            byte_order=str(raw.get("byte_order") or "little_endian"),
            factor=factor,
            offset=_number(raw.get("offset_value"), 0.0),
            behavior_type=behavior_type,
            model_label=model_label,
            parameters={**configuration, **_mapping(behavior.get("parameters")), **behavior},
            dependencies=dependencies,
            domain=str(raw.get("domain") or "generic"),
            data_type=str(raw.get("data_type") or data.get("datatype") or "unsigned"),
            invalid_value=(
                _number(data.get("invalid_value"), 0.0)
                if data.get("invalid_value") is not None
                else None
            ),
            enum_values={str(key): int(value) for key, value in _mapping(data.get("enum") or configuration.get("enum")).items()},
        )


@dataclass(frozen=True)
class SignalDependency:
    source_signal_id: str
    target_signal_id: str
    formula: str | None = None


class SignalBehaviorEngine:
    def __init__(self, signals: list[SignalDefinition], *, seed: int = 42) -> None:
        self.signals = signals
        self.seed = seed
        self._state: dict[str, float] = {}
        self._history: dict[str, list[tuple[float, float]]] = defaultdict(list)

    def sample(self, signal: SignalDefinition, time_s: float, context: dict[str, float] | None = None) -> float:
        return self.generate_signal_value(signal, time_s, context or {})

    def generate_signal_value(self, signal: SignalDefinition, time_s: float, context: dict[str, float]) -> float:
        params = signal.parameters
        minimum, maximum = signal.minimum, signal.maximum
        span = maximum - minimum
        midpoint = (minimum + maximum) / 2.0
        period = max(1e-9, _number(params.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
        phase = _number(params.get("phase"), 0.0)
        index = max(0, round(time_s * 1000.0 / signal.cycle_ms))
        rng = random.Random(_stable_seed(self.seed, signal.id, index))
        behavior = signal.behavior_type
        if behavior == "CONSTANT":
            value = _number(params.get("value"), midpoint)
        elif behavior == "STEP":
            value = _number(params.get("before"), minimum) if time_s < _number(params.get("at_s"), period / 2) else _number(params.get("after"), maximum)
        elif behavior in {"RAMP", "LINEAR"}:
            slope = _number(params.get("slope"), span / period)
            value = _number(params.get("start"), minimum) + slope * time_s
        elif behavior == "SINE":
            amplitude = _number(params.get("amplitude"), span * 0.4)
            value = _number(params.get("center"), midpoint) + amplitude * math.sin(2 * math.pi * time_s / period + phase)
        elif behavior == "TRIANGLE":
            fraction = ((time_s / period) + phase) % 1.0
            value = minimum + span * (1.0 - abs(2.0 * fraction - 1.0))
        elif behavior == "SAWTOOTH":
            value = minimum + span * (((time_s / period) + phase) % 1.0)
        elif behavior == "PULSE":
            duty = _clamp(_number(params.get("duty_cycle"), 0.5), 0.0, 1.0)
            value = maximum if ((time_s / period) + phase) % 1.0 < duty else minimum
        elif behavior == "RANDOM_WALK":
            previous = self._state.get(signal.id, midpoint)
            value = previous + rng.uniform(-span * 0.025, span * 0.025)
        elif behavior == "STATE_DEPENDENT":
            dependency_values = [float((context or {}).get(item, midpoint)) for item in signal.dependencies]
            value = sum(dependency_values) / len(dependency_values) if dependency_values else midpoint
        elif behavior == "FORMULA":
            variables = {"t": time_s, "min": minimum, "max": maximum, "mid": midpoint, **(context or {})}
            value = FormulaEvaluator.evaluate(str(params.get("formula") or "mid"), variables)
        elif behavior in {"LOOKUP_TABLE", "EXTERNAL_SERIES"}:
            points = _sequence(params.get("points") or params.get("series"))
            normalized = sorted(
                (_number(point.get("time_s"), 0.0), _number(point.get("value"), midpoint))
                for point in points if isinstance(point, dict)
            )
            value = midpoint
            for point_time, point_value in normalized:
                if point_time > time_s:
                    break
                value = point_value
        else:  # BOUNDED_RANDOM
            value = rng.uniform(minimum, maximum)
        value = self.apply_limits(signal, value)
        value = self.apply_resolution(signal, value)
        self.advance_state(signal, time_s, value)
        return value

    @staticmethod
    def apply_resolution(signal: SignalDefinition, value: float) -> float:
        return round(value / signal.resolution) * signal.resolution

    @staticmethod
    def apply_limits(signal: SignalDefinition, value: float) -> float:
        return _clamp(value, signal.minimum, signal.maximum)

    def apply_normal_profile(self, signal: SignalDefinition, time_s: float) -> float:
        return self.generate_signal_value(signal, time_s, {})

    def apply_dependencies(self, signal: SignalDefinition, time_s: float, values: dict[str, float]) -> float:
        return self.generate_signal_value(signal, time_s, values)

    @staticmethod
    def apply_signal_fault(value: float | None) -> float | None:
        return value

    def advance_state(self, signal: SignalDefinition, time_s: float, value: float) -> None:
        self._state[signal.id] = value
        self._history[signal.id].append((time_s, value))

    def delayed(self, signal_id: str, time_s: float, delay_s: float, fallback: float) -> float:
        target = time_s - delay_s
        prior = [value for timestamp, value in self._history.get(signal_id, []) if timestamp <= target]
        return prior[-1] if prior else fallback


class FunctionBehaviorEngine:
    """Resolve dependent signal functions against already sampled inputs."""

    def evaluate(self, signal: SignalDefinition, time_s: float, values: dict[str, float], engine: SignalBehaviorEngine) -> float:
        context = {key.replace("-", "_"): value for key, value in values.items()}
        return engine.sample(signal, time_s, context)


class FaultInjectionEngine:
    def __init__(self, faults: list[dict[str, Any]], *, seed: int) -> None:
        self.faults = [item for item in faults if isinstance(item, dict) and item.get("enabled", True)]
        self.seed = seed
        self._frozen: dict[str, float] = {}

    @staticmethod
    def _active(fault: dict[str, Any], time_s: float) -> bool:
        return _number(fault.get("start_s"), 0.0) <= time_s <= _number(fault.get("end_s"), float("inf"))

    @staticmethod
    def _target_matches(fault: dict[str, Any], *, object_id: str, name: str = "", domain: str = "") -> bool:
        target = _mapping(fault.get("target"))
        expected = str(target.get("id") or target.get("name") or target.get("signal_id") or target.get("message_id") or target.get("network_id") or "")
        if expected and expected not in {object_id, name}:
            return False
        expected_domain = str(target.get("domain") or "").lower()
        return not expected_domain or expected_domain == domain.lower()

    def signal_value(self, signal: SignalDefinition, time_s: float, baseline: float, behavior: SignalBehaviorEngine) -> tuple[float | None, list[str]]:
        value: float | None = baseline
        applied: list[str] = []
        for fault in self.faults:
            fault_type = normalize_fault_type(fault.get("type"))
            if fault_type not in SIGNAL_FAULTS or not self._active(fault, time_s) or not self._target_matches(fault, object_id=signal.id, name=signal.name, domain=signal.domain):
                continue
            magnitude = _number(fault.get("magnitude"), (signal.maximum - signal.minimum) * 0.1)
            if fault_type in {"SIGNAL_STUCK", "SIGNAL_FROZEN"}:
                value = self._frozen.setdefault(signal.id, baseline)
            elif fault_type == "SIGNAL_OFFSET":
                value = (value if value is not None else baseline) + magnitude
            elif fault_type == "SIGNAL_DRIFT":
                value = (value if value is not None else baseline) + magnitude * max(0.0, time_s - _number(fault.get("start_s"), 0.0))
            elif fault_type == "SIGNAL_SPIKE":
                value = (value if value is not None else baseline) + magnitude
            elif fault_type == "SIGNAL_DROPOUT":
                value = None
            elif fault_type == "SIGNAL_NOISE":
                rng = random.Random(_stable_seed(self.seed, signal.id, fault_type, time_s))
                value = (value if value is not None else baseline) + rng.gauss(0.0, abs(magnitude))
            elif fault_type == "SIGNAL_OUT_OF_RANGE":
                value = signal.maximum + abs(magnitude)
            elif fault_type == "SIGNAL_DELAYED":
                value = behavior.delayed(signal.id, time_s, max(0.0, _number(fault.get("delay_s"), 0.1)), baseline)
            elif fault_type == "SIGNAL_WRONG_SCALE":
                value = (value if value is not None else baseline) * _number(fault.get("scale"), 2.0)
            elif fault_type == "SIGNAL_INVALID_VALUE":
                value = None
            applied.append(fault_type)
        return value, applied

    def event_faults(self, event: dict[str, Any]) -> list[str]:
        time_s = float(event.get("scheduled_time_s") or 0.0)
        applied: list[str] = []
        for fault in self.faults:
            fault_type = normalize_fault_type(fault.get("type"))
            valid = fault_type in MESSAGE_FAULTS or fault_type in NETWORK_FAULTS
            target_id = str(event.get("route_id") if fault_type in MESSAGE_FAULTS else event.get("network"))
            expected_target = str(_mapping(fault.get("target")).get("id") or "")
            message_targets = {str(item) for item in _sequence(event.get("message_ids"))}
            target_matches = self._target_matches(fault, object_id=target_id, name=str(event.get("route_name") or "")) or bool(expected_target and expected_target in message_targets)
            if not valid or not self._active(fault, time_s) or not target_matches:
                continue
            if fault_type in {"MESSAGE_LOSS", "BUS_OFF", "LINK_DOWN", "GATEWAY_DROP", "TEMPORARY_DISCONNECT", "ROUTING_FAILURE"}:
                event["status"] = "dropped"
                event["drop_reason"] = fault_type.lower()
            elif fault_type in {"MESSAGE_DELAY", "GATEWAY_DELAY", "CONGESTION", "MESSAGE_TIMEOUT"}:
                event["configured_latency_ms"] = float(event.get("configured_latency_ms") or 0.0) + _number(fault.get("delay_ms"), 50.0)
            elif fault_type == "MESSAGE_JITTER":
                event["injected_jitter_ms"] = float(event.get("injected_jitter_ms") or 0.0) + _number(fault.get("jitter_ms"), 10.0)
            elif fault_type in {"MESSAGE_CORRUPTION", "FRAME_ERROR"}:
                event["status"] = "corrupted"
                payload = str(event.get("payload_hex") or "")
                event["payload_hex"] = "FF" + payload[2:] if payload else "FF"
            elif fault_type == "MESSAGE_DUPLICATION":
                event["duplicate_injected"] = True
            elif fault_type in {"NETWORK_OVERLOAD", "BURST_TRAFFIC", "QUEUE_OVERFLOW"}:
                event["fault_load_multiplier"] = max(1.0, _number(fault.get("factor"), 4.0))
                if fault_type == "QUEUE_OVERFLOW":
                    event["status"] = "dropped"
                    event["drop_reason"] = "queue_overflow"
            elif fault_type == "MESSAGE_WRONG_CYCLE":
                event["configured_cycle_ms"] = max(0.001, _number(fault.get("cycle_ms"), float(event.get("configured_cycle_ms") or 1.0) * 2))
            applied.append(fault_type)
        return applied


class MessageCodec:
    @staticmethod
    def encode(signals: list[tuple[SignalDefinition, float | None]], payload_bytes: int) -> str:
        byte_count = max(1, payload_bytes)
        bit_count = byte_count * 8
        payload = bytearray(byte_count)
        for signal, value in signals:
            physical_value = signal.invalid_value if value is None else value
            if physical_value is None or signal.start_bit >= bit_count:
                continue
            length = min(signal.length_bits, bit_count - signal.start_bit)
            raw = int(round((physical_value - signal.offset) / signal.factor))
            signed = "int" in signal.data_type.lower() and "uint" not in signal.data_type.lower() or "signed" in signal.data_type.lower()
            if signed:
                raw = max(-(1 << (length - 1)), min((1 << (length - 1)) - 1, raw))
                if raw < 0:
                    raw = (1 << length) + raw
            else:
                raw = max(0, min((1 << length) - 1, raw))
            if signal.byte_order == "big_endian" and signal.start_bit % 8 == 0 and length % 8 == 0:
                start = signal.start_bit // 8
                payload[start:start + length // 8] = raw.to_bytes(length // 8, "big")
            else:
                raw_payload = int.from_bytes(payload, "little")
                raw_payload &= ~(((1 << length) - 1) << signal.start_bit)
                raw_payload |= raw << signal.start_bit
                payload[:] = raw_payload.to_bytes(byte_count, "little")
        return bytes(payload).hex(" ").upper()

    @staticmethod
    def decode(payload_hex: str, signal: SignalDefinition) -> float:
        data = bytes.fromhex(payload_hex)
        if signal.byte_order == "big_endian" and signal.start_bit % 8 == 0 and signal.length_bits % 8 == 0:
            start = signal.start_bit // 8
            raw = int.from_bytes(data[start:start + signal.length_bits // 8], "big")
        else:
            raw_payload = int.from_bytes(data, byteorder="little", signed=False)
            raw = (raw_payload >> signal.start_bit) & ((1 << signal.length_bits) - 1)
        signed = "int" in signal.data_type.lower() and "uint" not in signal.data_type.lower() or "signed" in signal.data_type.lower()
        if signed and raw & (1 << (signal.length_bits - 1)):
            raw -= 1 << signal.length_bits
        return raw * signal.factor + signal.offset


class MessageEncoder(MessageCodec):
    """Named extension point for protocol-specific message encoders/decoders."""


class ModelBasedSimulationEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        model = _mapping(config.get("engineering_model"))
        messages = {str(item.get("id")): item for item in _sequence(model.get("messages")) if isinstance(item, dict)}
        behavior_by_signal = {
            str(item.get("signal_id")): item
            for item in _sequence(model.get("behaviors")) if isinstance(item, dict)
        }
        raw_signals = []
        for item in _sequence(model.get("signals")):
            if not isinstance(item, dict):
                continue
            behavior = behavior_by_signal.get(str(item.get("id")))
            raw_signals.append({**item, **({"behavior": behavior} if behavior else {})})
        self.signals = [SignalDefinition.from_record(item, messages.get(str(item.get("message_id")))) for item in raw_signals]
        self.by_id = {signal.id: signal for signal in self.signals}
        self.by_message: dict[str, list[SignalDefinition]] = defaultdict(list)
        for signal in self.signals:
            self.by_message[signal.message_id].append(signal)
        self.seed = int(config.get("seed") or 42)
        scenario = _mapping(config.get("scenario"))
        scenario_mode = str(scenario.get("mode") or "NORMAL").upper()
        self.behavior = SignalBehaviorEngine(self.signals, seed=self.seed)
        self.functions = FunctionBehaviorEngine()
        configured_faults = [] if scenario_mode == "NORMAL" else _sequence(scenario.get("faults") or config.get("faults"))
        self.faults = FaultInjectionEngine(configured_faults, seed=self.seed)
        self.codec = MessageCodec()

    def route_signals(self, route: dict[str, Any]) -> list[SignalDefinition]:
        metadata = _mapping(route.get("metadata"))
        signal_ids = [str(item) for item in _sequence(metadata.get("signal_ids"))]
        if signal_ids:
            return [self.by_id[item] for item in signal_ids if item in self.by_id]
        message_id = str(metadata.get("message_id") or "")
        if message_id and self.by_message.get(message_id):
            return self.by_message[message_id]
        sender_interface = str(_mapping(route.get("sender")).get("interface_id") or "")
        engineering = _mapping(metadata.get("engineering"))
        message_ids = [str(item) for item in _sequence(engineering.get("message_ids"))]
        if message_ids:
            return [signal for message in message_ids for signal in self.by_message.get(message, [])]
        candidates = [signal for signal in self.signals if str(signal.parameters.get("interface_id") or "") == sender_interface]
        return candidates

    def encode_event(self, route: dict[str, Any], time_s: float, payload_bytes: int) -> dict[str, Any]:
        values: dict[str, float] = {}
        encoded: list[tuple[SignalDefinition, float | None]] = []
        samples: list[dict[str, Any]] = []
        for signal in self.route_signals(route):
            baseline = self.functions.evaluate(signal, time_s, values, self.behavior)
            value, faults = self.faults.signal_value(signal, time_s, baseline, self.behavior)
            if value is not None:
                values[signal.id] = value
                values[signal.name] = value
            encoded.append((signal, value))
            samples.append({
                "signal_id": signal.id, "signal": signal.name, "value": value,
                "golden_value": baseline, "unit": signal.unit, "minimum": signal.minimum,
                "maximum": signal.maximum, "resolution": signal.resolution,
                "cycle_ms": signal.cycle_ms, "behavior_type": signal.behavior_type,
                "model_label": signal.model_label, "faults": faults,
                "received_value": self.codec.decode(self.codec.encode([(signal, value)], payload_bytes), signal) if value is not None or signal.invalid_value is not None else None,
            })
        return {"payload_hex": self.codec.encode(encoded, payload_bytes), "signals": samples}


def build_model_trace(events: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    signal_series: dict[str, dict[str, Any]] = {}
    synchronized_events: list[dict[str, Any]] = []
    frame_limit = _trace_limit(config, "model_trace_frame_limit", DEFAULT_MODEL_TRACE_FRAME_LIMIT)
    signal_point_limit = _trace_limit(config, "model_trace_signal_point_limit", DEFAULT_MODEL_TRACE_SIGNAL_POINT_LIMIT)
    synchronized_event_limit = _trace_limit(config, "model_trace_event_limit", DEFAULT_MODEL_TRACE_EVENT_LIMIT)
    total_signal_samples = 0
    stored_signal_samples = 0
    total_synchronized_events = 0
    synchronized_warning_count = 0
    synchronized_error_count = 0
    deltas: list[float] = []
    load_buckets: dict[tuple[str, int], float] = defaultdict(float)
    load_window_s = 0.05
    frame_timeline: list[dict[str, Any]] = []

    def add_synchronized_event(item: dict[str, Any]) -> None:
        nonlocal synchronized_error_count, synchronized_warning_count, total_synchronized_events
        total_synchronized_events += 1
        if item.get("severity") == "ERROR":
            synchronized_error_count += 1
        elif item.get("severity") == "WARNING":
            synchronized_warning_count += 1
        if synchronized_event_limit == 0 or len(synchronized_events) < synchronized_event_limit:
            synchronized_events.append(item)

    for event in events:
        time_s = float(event.get("time_s") or 0.0)
        network_id = str(event.get("network") or "unknown")
        if event.get("status") != "dropped":
            load_buckets[(network_id, int(time_s / load_window_s))] += float(event.get("transmission_latency_ms") or 0.0) / 1000.0
        if frame_limit == 0 or len(frame_timeline) < frame_limit:
            frame_timeline.append({
                "time_s": time_s,
                "route_id": event.get("route_id"),
                "route_name": event.get("route_name"),
                "network": network_id,
                "technology": event.get("technology"),
                "status": event.get("status"),
                "sender": event.get("sender_hardware"),
                "receivers": event.get("receiver_hardware") or [],
                "payload_bytes": event.get("payload_bytes"),
                "transmission_latency_ms": event.get("transmission_latency_ms"),
                "end_to_end_latency_ms": event.get("end_to_end_latency_ms"),
                "queue_depth_estimate": event.get("queue_depth_estimate"),
                "queue_delay_ms": event.get("queue_delay_ms"),
                "configured_cycle_ms": event.get("configured_cycle_ms"),
                "gateway_ids": event.get("gateway_ids") or [],
                "faults": event.get("faults") or [],
                "drop_reason": event.get("drop_reason"),
                "retransmission_count": event.get("retransmission_count"),
                "duplicate_injected": event.get("duplicate_injected"),
                "reordered": event.get("reordered"),
            })
        for sample in _sequence(event.get("signals")):
            if not isinstance(sample, dict):
                continue
            signal_id = str(sample.get("signal_id"))
            series = signal_series.setdefault(signal_id, {key: sample.get(key) for key in ("signal_id", "signal", "unit", "minimum", "maximum", "resolution", "cycle_ms", "behavior_type", "model_label")})
            series.setdefault("points", [])
            total_signal_samples += 1
            if signal_point_limit == 0 or stored_signal_samples < signal_point_limit:
                series["points"].append({"time_s": event.get("time_s"), "value": sample.get("value"), "golden_value": sample.get("golden_value"), "faults": sample.get("faults") or []})
                stored_signal_samples += 1
            if isinstance(sample.get("value"), (int, float)) and isinstance(sample.get("golden_value"), (int, float)):
                deltas.append(float(sample["value"]) - float(sample["golden_value"]))
            if sample.get("faults"):
                add_synchronized_event({
                    "time_s": event.get("time_s"), "severity": "WARNING", "event_type": "SIGNAL_FAULT_ACTIVE",
                    "scope": "SIGNAL", "target": sample.get("signal"), "node": event.get("sender_hardware"),
                    "message": event.get("route_name"), "signal": sample.get("signal"), "network": event.get("network"),
                    "description": ", ".join(str(item) for item in sample.get("faults") or []),
                    "faults": sample.get("faults"),
                })
        if event.get("faults") or event.get("status") != "transmitted":
            add_synchronized_event({
                "time_s": event.get("time_s"), "severity": "ERROR" if event.get("status") in {"dropped", "corrupted"} else "WARNING",
                "event_type": "TRANSPORT_FAULT", "scope": "FRAME", "target": event.get("route_name"),
                "node": event.get("sender_hardware"), "message": event.get("route_name"),
                "signal": event.get("signal"), "network": event.get("network"),
                "description": str(event.get("drop_reason") or event.get("status") or "Fault"),
                "faults": event.get("faults") or [event.get("status")],
            })
    scenario = _mapping(config.get("scenario"))
    for fault in _sequence(scenario.get("faults")):
        if not isinstance(fault, dict):
            continue
        target = _mapping(fault.get("target"))
        for phase, timestamp in (("FAULT_START", fault.get("start_s")), ("FAULT_END", fault.get("end_s"))):
            if timestamp is None:
                continue
            add_synchronized_event({
                "time_s": float(timestamp), "severity": "WARNING", "event_type": phase,
                "scope": str(fault.get("scope") or "UNKNOWN"), "target": target.get("name") or target.get("id") or "all",
                "node": target.get("node_id"), "message": target.get("message_id"), "signal": target.get("signal_id"),
                "network": target.get("network_id"), "description": str(fault.get("type") or "Fault"),
                "faults": [str(fault.get("type") or "Fault")],
            })
    ordered_events = sorted(synchronized_events, key=lambda item: float(item.get("time_s") or 0.0))
    changed_samples = sum(1 for delta in deltas if abs(delta) > 1e-12)
    affected_signals = sorted({
        str(item.get("signal"))
        for item in ordered_events
        if item.get("signal") and item.get("scope") == "SIGNAL"
    })
    affected_routes = sorted({
        str(event.get("route_id"))
        for event in events
        if event.get("route_id") and (event.get("faults") or event.get("status") != "transmitted")
    })
    transmitted_frames = sum(1 for event in events if event.get("status") == "transmitted")
    dropped_frames = sum(1 for event in events if event.get("status") == "dropped")
    configured_faults = [item for item in _sequence(scenario.get("faults")) if isinstance(item, dict)]
    warning_count = synchronized_warning_count
    error_count = synchronized_error_count
    bus_load = [
        {
            "network_id": network_id,
            "time_s": (bucket + 1) * load_window_s,
            "load_percent": busy_s / load_window_s * 100.0,
            "window_ms": load_window_s * 1000.0,
        }
        for (network_id, bucket), busy_s in sorted(load_buckets.items(), key=lambda item: (item[0][1], item[0][0]))
    ]
    load_values = [float(item["load_percent"]) for item in bus_load]
    load_by_network = {
        network_id: [float(item["load_percent"]) for item in bus_load if item["network_id"] == network_id]
        for network_id in sorted({str(item["network_id"]) for item in bus_load})
    }
    return {
        "schema": "communication-simulator.model-trace.v1",
        "scenario": {
            "name": scenario.get("name") or "Normalbetrieb",
            "mode": scenario.get("mode") or "NORMAL",
            "duration_s": config.get("duration_s"),
            "speed": scenario.get("speed") or 1,
            "seed": config.get("seed"),
            "trace_formats": config.get("formats") or [],
        },
        "signals": list(signal_series.values()),
        "events": ordered_events,
        "frames": frame_timeline,
        "bus_load": bus_load,
        "comparison": {
            "available": bool(deltas),
            "changed_samples": changed_samples,
            "rmse": math.sqrt(sum(delta * delta for delta in deltas) / len(deltas)) if deltas else 0.0,
            "baseline": "golden",
            "candidate": "fault" if _sequence(scenario.get("faults")) else "normal",
        },
        "signal_summary": {
            "signal_count": len(signal_series),
            "sample_count": total_signal_samples,
            "stored_sample_count": stored_signal_samples,
            "changed_samples": changed_samples,
            "affected_signals": affected_signals,
        },
        "fault_summary": {
            "configured_faults": len(configured_faults),
            "active_events": len(ordered_events),
            "warning_count": warning_count,
            "error_count": error_count,
            "fault_types": sorted({str(item.get("type")) for item in configured_faults if item.get("type")}),
        },
        "timing_summary": {
            "frame_count": len(events),
            "stored_frame_count": len(frame_timeline),
            "transmitted_frames": transmitted_frames,
            "dropped_frames": dropped_frames,
            "duration_s": config.get("duration_s"),
            "load_window_ms": load_window_s * 1000.0,
        },
        "network_load_summary": {
            "average_percent": sum(load_values) / len(load_values) if load_values else 0.0,
            "peak_percent": max(load_values, default=0.0),
            "burst_percent": max(
                (sum(values[index:index + 3]) / len(values[index:index + 3]) for values in load_by_network.values() for index in range(len(values))),
                default=0.0,
            ),
            "networks": {
                network_id: {
                    "average_percent": sum(values) / len(values),
                    "peak_percent": max(values),
                }
                for network_id, values in load_by_network.items()
            },
        },
        "first_anomaly": ordered_events[0] if ordered_events else None,
        "affected_routes": affected_routes,
        "affected_signals": affected_signals,
        "warnings": warning_count,
        "errors": error_count,
        "storage": {
            "truncated": len(frame_timeline) < len(events) or stored_signal_samples < total_signal_samples or len(ordered_events) < total_synchronized_events,
            "frame_limit": frame_limit,
            "signal_point_limit": signal_point_limit,
            "event_limit": synchronized_event_limit,
            "stored_frames": len(frame_timeline),
            "total_frames": len(events),
            "stored_signal_points": stored_signal_samples,
            "total_signal_points": total_signal_samples,
            "stored_events": len(ordered_events),
            "total_events": total_synchronized_events,
        },
        "model_labels": sorted({str(series.get("model_label")) for series in signal_series.values()}),
        "clock": "simulation_time_s",
    }


def fault_catalog() -> dict[str, list[dict[str, Any]]]:
    categories = {"signal": SIGNAL_FAULTS, "message": MESSAGE_FAULTS, "network": NETWORK_FAULTS}
    return {
        category: [
            {
                "id": fault_id,
                "name": fault_id.replace("_", " ").title(),
                "category": category.upper(),
                "applicable_object_types": [category.upper()],
                "parameters": ["start_s", "end_s", "magnitude", "target"],
                "constraints": {"start_s": {"minimum": 0}, "end_s": {"after": "start_s"}},
                "simulation_handler": "FaultInjectionEngine",
            }
            for fault_id in fault_ids
        ]
        for category, fault_ids in categories.items()
    }


class FaultCatalog:
    def all(self) -> dict[str, list[dict[str, Any]]]:
        return fault_catalog()

    def describe(self, fault_id: str) -> dict[str, Any] | None:
        normalized = normalize_fault_type(fault_id)
        return next(
            (item for items in self.all().values() for item in items if item["id"] == normalized),
            None,
        )


def demo_scenarios() -> list[dict[str, Any]]:
    golden_profiles = [
        {"signal": "Temperature", "behavior_type": "LOOKUP_TABLE", "points": [{"time_s": 0, "value": 20}, {"time_s": 30, "value": 60}, {"time_s": 80, "value": 60}]},
        {"signal": "MotorRPM", "behavior_type": "LOOKUP_TABLE", "points": [{"time_s": 0, "value": 0}, {"time_s": 15, "value": 3000}, {"time_s": 30, "value": 4500}, {"time_s": 80, "value": 2000}]},
        {"signal": "MotorCurrent", "behavior_type": "FORMULA", "formula": "MotorRPM * 0.02", "dependencies": ["MotorRPM"]},
    ]
    return [
        {"id": "DEMO_A_GOLDEN", "name": "Golden temperature and motion", "mode": "NORMAL", "duration_s": 80, "signal_profiles": golden_profiles, "faults": [], "expected_behavior": {"injected_faults": 0}},
        {"id": "DEMO_B_RPM_LIMIT", "name": "RPM limit exceeded", "mode": "USER_DEFINED_FAULT", "duration_s": 80, "signal_profiles": golden_profiles, "faults": [{"scope": "SIGNAL", "type": "SIGNAL_SPIKE", "target": {"name": "MotorRPM"}, "start_s": 30, "end_s": 30.5, "magnitude": 700}], "expected_behavior": {"event": "RPM_LIMIT_EXCEEDED"}},
        {"id": "DEMO_C_TEMPERATURE_FROZEN", "name": "Temperature sensor frozen", "mode": "USER_DEFINED_FAULT", "duration_s": 80, "signal_profiles": golden_profiles, "faults": [{"scope": "SIGNAL", "type": "SIGNAL_FROZEN", "target": {"name": "Temperature"}, "start_s": 40, "end_s": 50, "value": 61}], "expected_behavior": {"actual_model_continues": True}},
        {"id": "DEMO_D_MESSAGE_LOSS", "name": "Motion status message loss", "mode": "USER_DEFINED_FAULT", "duration_s": 80, "signal_profiles": golden_profiles, "faults": [{"scope": "MESSAGE", "type": "MESSAGE_LOSS", "target": {"name": "MSG_MOTION_STATUS"}, "start_s": 50, "end_s": 52}], "expected_behavior": {"event": "TIMEOUT", "stale_signal": True}},
        {"id": "DEMO_E_AI_CAMPAIGN", "name": "AI fault campaign", "mode": "AI_GENERATED_FAULT", "duration_s": 80, "signal_profiles": golden_profiles, "faults": [], "proposal_count": 3, "requires_review": True, "expected_behavior": {"reproducible_after_review": True}},
    ]
