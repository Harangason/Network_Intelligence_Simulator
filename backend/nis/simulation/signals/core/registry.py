from __future__ import annotations

import ast
import math
import operator
import random
from typing import Any, Callable

from backend.nis.simulation.signals.core.context import SimulationContext
from backend.nis.simulation.signals.core.runtime_state import SignalRuntimeState
from backend.nis.simulation.signals.core.registry_utils import stable_seed
from backend.nis.simulation.signals.mathematical import bounded_random as bounded_random
from backend.nis.simulation.signals.mathematical import constant as constant
from backend.nis.simulation.signals.mathematical import number
from backend.nis.simulation.signals.mathematical import pulse as pulse
from backend.nis.simulation.signals.mathematical import ramp as ramp
from backend.nis.simulation.signals.mathematical import random_walk as random_walk
from backend.nis.simulation.signals.mathematical import sine as sine
from backend.nis.simulation.signals.mathematical import step as step
from backend.nis.simulation.signals.mathematical import triangle as triangle
from backend.nis.simulation.signals.physical import PhysicalModelRegistry
from backend.nis.simulation.signals.status_models import StatusModelRegistry


def number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class SafeFormula:
    _operators = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    _functions = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt, "abs": abs, "min": min, "max": max}

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


BehaviorHandler = Callable[[Any, float, SimulationContext, SignalRuntimeState], float]


class SignalBehaviorRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, BehaviorHandler] = {}
        self.status_models = StatusModelRegistry()
        self.physical_models = PhysicalModelRegistry()
        self.register_defaults()

    @classmethod
    def get_function_block_standard(cls, standard_id):
        from copy import deepcopy
        import hashlib
        import json
        from pathlib import Path
        from backend.nis.simulation.signals.core.function_block import QwenFunctionBlock
        path = Path(__file__).with_name('function_block_standards.json')
        content = path.read_bytes()
        document = json.loads(content)
        if document.get('owner') != 'SignalBehaviorRegistry' or document.get('schema_version') != 1:
            raise ValueError('Unsupported function standard catalog contract.')
        standards = document.get('standards')
        if not isinstance(standards, list) or not 1 <= len(standards) <= 64:
            raise ValueError('Invalid function standard catalog.')
        identifiers = [row['id'].casefold() for row in standards]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('Duplicate function standard identities.')
        selected = next((row for row in standards if row['id'].casefold() == str(standard_id).casefold()), None)
        if selected is None:
            raise ValueError('Unknown function standard: ' + str(standard_id))
        result = deepcopy(selected)
        QwenFunctionBlock(result['definition'])
        if (result['definition'].get('provenance') or {}).get('generated_by') != 'QWEN':
            raise ValueError('Function standards require QWEN authorship.')
        result['definition']['standard_origin'] = {'owner':'SignalBehaviorRegistry', 'standard_id':selected['id'],
            'catalog_sha256':hashlib.sha256(content).hexdigest(),'catalog_version':document['schema_version'],
            'source_sha256':result['definition']['source_sha256']}
        return result

    @classmethod
    def function_block_standards(cls, standard_id=None, include_source=False):
        import json
        from pathlib import Path
        identifiers = ([standard_id] if standard_id is not None else
            [row['id'] for row in json.loads(Path(__file__).with_name('function_block_standards.json').read_bytes())['standards']])
        result = []
        for identifier in identifiers:
            selected = cls.get_function_block_standard(identifier)
            definition = selected['definition']
            item = {'id':selected['id'],'description':definition['description'],'input_types':selected['input_types'],
                'parameter_schema':definition['parameter_schema'],'parameter_relations':definition.get('parameter_relations') or [],
                'source_sha256':definition['source_sha256'],'origin':definition['standard_origin'],
                'logic_rule':definition.get('logic_rule'),'author':'QWEN'}
            if include_source:
                item['source_code'] = definition['source_code']
            result.append(item)
        return {'owner':'SignalBehaviorRegistry','standards':result,
                'note':'Explicit input identities/types, parameters, full Boolean truth tables and project review are required. No automatic ECU assignment.'}


    def register(self, name: str, handler: BehaviorHandler) -> None:
        self._handlers[name.upper()] = handler

    def generate(self, signal: Any, time_s: float, context: SimulationContext, state: SignalRuntimeState) -> float:
        handler = self._handlers.get(str(signal.behavior_type).upper(), self._handlers["BOUNDED_RANDOM"])
        return handler(signal, time_s, context, state)

    def register_defaults(self) -> None:
        self.register("CONSTANT", constant)
        self.register("STEP", step)
        self.register("RAMP", ramp)
        self.register("LINEAR", ramp)
        self.register("SINE", sine)
        self.register("TRIANGLE", triangle)
        self.register("SAWTOOTH", sawtooth)
        self.register("PULSE", pulse)
        self.register("RANDOM_WALK", random_walk)
        self.register("BOUNDED_RANDOM", bounded_random)
        self.register("STATE_DEPENDENT", state_dependent)
        self.register("FORMULA", formula)
        self.register("LOOKUP_TABLE", lookup)
        self.register("EXTERNAL_SERIES", lookup)
        self.register("PHYSICS_MODEL", physical)
        self.register("STATE_MACHINE", self.status_models.generate)
        self.register("STATUS_MODEL", self.status_models.generate)
        self.register("FUNCTION_BLOCK", received_function_placeholder)


def received_function_placeholder(signal, _time_s, _context, _state):
    # The transport pass evaluates once inputs are actually received. A random
    # fallback would invent function behavior before that execution boundary.
    from backend.nis.simulation.signals.core.function_block import validate_function_spec
    validate_function_spec(signal.parameters)
    return float(signal.parameters['invalid_output'])


def bounds(signal: Any) -> tuple[float, float, float, float]:
    minimum = float(signal.minimum)
    maximum = float(signal.maximum)
    span = max(1e-9, maximum - minimum)
    return minimum, maximum, span, (minimum + maximum) / 2.0


def sawtooth(signal: Any, time_s: float, _context: SimulationContext, _state: SignalRuntimeState) -> float:
    minimum, _maximum, span, _midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    return minimum + span * (((time_s / period) + number(signal.parameters.get("phase"), 0.0)) % 1.0)


def pulse(signal: Any, time_s: float, _context: SimulationContext, _state: SignalRuntimeState) -> float:
    minimum, maximum, _span, _midpoint = bounds(signal)
    period = max(1e-9, number(signal.parameters.get("period_s"), max(signal.cycle_ms / 1000.0 * 20, 1.0)))
    duty = clamp(number(signal.parameters.get("duty_cycle"), 0.5), 0.0, 1.0)
    return maximum if ((time_s / period) + number(signal.parameters.get("phase"), 0.0)) % 1.0 < duty else minimum


def random_walk(signal: Any, time_s: float, context: SimulationContext, state: SignalRuntimeState) -> float:
    minimum, _maximum, span, midpoint = bounds(signal)
    dt = state.dt(signal.id, time_s, signal.cycle_ms / 1000.0)
    index = int(time_s * 1000.0 / max(signal.cycle_ms, 0.001))
    rng = random.Random(stable_seed(context.seed, signal.id, index))
    previous = state.previous(signal.id, number(signal.parameters.get("initial_value"), midpoint))
    step_size = number(signal.parameters.get("step"), span * 0.01)
    return previous + rng.uniform(-step_size, step_size) * max(1.0, dt / max(signal.cycle_ms / 1000.0, 0.001))


def bounded_random(signal: Any, time_s: float, context: SimulationContext, state: SignalRuntimeState) -> float:
    return random_walk(signal, time_s, context, state)


def state_dependent(signal: Any, _time_s: float, context: SimulationContext, _state: SignalRuntimeState) -> float:
    _minimum, _maximum, _span, midpoint = bounds(signal)
    dependency_values = [float(context.signal_values.get(item, midpoint)) for item in signal.dependencies]
    return sum(dependency_values) / len(dependency_values) if dependency_values else midpoint


def formula(signal: Any, time_s: float, context: SimulationContext, _state: SignalRuntimeState) -> float:
    _minimum, _maximum, _span, midpoint = bounds(signal)
    variables = {"t": time_s, "min": signal.minimum, "max": signal.maximum, "mid": midpoint, **context.signal_values}
    return SafeFormula.evaluate(str(signal.parameters.get("formula") or "mid"), variables)


def lookup(signal: Any, time_s: float, _context: SimulationContext, _state: SignalRuntimeState) -> float:
    _minimum, _maximum, _span, midpoint = bounds(signal)
    points = signal.parameters.get("points") or signal.parameters.get("series")
    normalized = sorted(
        (number(point.get("time_s"), 0.0), number(point.get("value"), midpoint))
        for point in points if isinstance(point, dict)
    ) if isinstance(points, list) else []
    value = midpoint
    for point_time, point_value in normalized:
        if point_time > time_s:
            break
        value = point_value
    return value


def physical(signal: Any, time_s: float, context: SimulationContext, state: SignalRuntimeState) -> float:
    name = str(signal.name).lower()
    if "command" in name or "request" in name:
        if "start" in name:
            return 1.0 if 0.5 <= time_s < 2.0 else 0.0
        if "stop" in name:
            return 1.0 if 55.0 <= time_s < 57.0 else 0.0
        if "throttle" in name or "pedal" in name:
            return clamp(0.2 + 0.45 * math.sin(time_s / 8.0) ** 2, signal.minimum, signal.maximum)
        return 1.0 if str(context.system_state.get("operating_state") or "") in {"STARTING", "RUNNING"} else 0.0
    if any(token in name for token in ("state", "status", "health", "safety", "quality", "counter", "alive", "enabled", "valid")) or signal.enum_values:
        return StatusModelRegistry().generate(signal, time_s, context, state)
    return PhysicalModelRegistry().generate(signal, time_s, context, state)
