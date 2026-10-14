"""Object-oriented, bounded execution of reviewed QWEN function code.

The interpreter implements a small Python subset. It never invokes exec/eval,
imports a generated module, or gives generated code a database/file handle.
"""
from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import operator
from typing import Any


@dataclass(frozen=True)
class BlockResult:
    value: float | bool
    state: dict[str, float | bool]
    source_sha256: str


class FunctionBlock(ABC):
    @abstractmethod
    def step(self, inputs: dict, parameters: dict, dt: float) -> BlockResult:
        """Advance one model instance using its own received inputs."""

    @abstractmethod
    def reset(self) -> None:
        """Reset this instance, never another ECU's state."""


_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Mod: operator.mod}
_COMPARE = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
            ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne,
            ast.In: lambda left, right: left in right,
            ast.NotIn: lambda left, right: left not in right}
_ALLOWED = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.arguments, ast.arg,
            ast.Assign, ast.Return, ast.If, ast.Expr, ast.Name, ast.Load, ast.Store,
            ast.Constant, ast.Subscript, ast.Attribute, ast.Call, ast.BinOp,
            ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Not, ast.USub,
            ast.UAdd, ast.And, ast.Or, *_BINARY.keys(), *_COMPARE.keys())


def _finite(value: Any) -> float | bool:
    if type(value) not in (int, float, bool) or not math.isfinite(value) or abs(value) > 1e100:
        raise ValueError('Function code requires bounded finite numeric/boolean values.')
    return value


def inspect_logic_expression(expression, bindings=None):
    """Parse the requested Boolean graph as data; execution remains QWEN code."""
    import io
    import tokenize
    if not isinstance(expression, str) or not expression.strip() or len(expression.encode()) > 4000:
        raise ValueError('Boolean expression must contain 1..4000 UTF-8 bytes.')
    aliases = {'AND':'and','UND':'and','OR':'or','ODER':'or','NOT':'not','NICHT':'not'}
    try:
        tokens = [(item.type, aliases.get(item.string.upper(), item.string)
                   if item.type == tokenize.NAME else item.string)
                  for item in tokenize.generate_tokens(io.StringIO(expression).readline)]
        normalized = tokenize.untokenize(tokens).strip()
        parsed = ast.parse(normalized, mode='eval')
    except (SyntaxError, tokenize.TokenError, IndentationError) as error:
        raise ValueError('Invalid Boolean expression; use explicit parentheses and XOR(A, B).') from error
    if len(list(ast.walk(parsed))) > 128:
        raise ValueError('Boolean expression exceeds the bounded graph limit.')
    names = set()
    join_sizes = []
    arities = {'XOR':(2,8),'NAND':(2,8),'NOR':(2,8),'XNOR':(2,8),'IMPLIES':(2,2),'SELECT':(3,3)}
    def graph(node):
        if isinstance(node, ast.Name) and node.id.isidentifier() and not node.id.startswith('_'):
            if node.id.upper() in {*aliases, *arities, 'JOIN', 'N'}:
                raise ValueError('Boolean input names cannot be reserved operators.')
            names.add(node.id)
            return {'input':node.id}
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return {'constant':node.value}
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return {'operator':'AND' if isinstance(node.op, ast.And) else 'OR', 'operands':[graph(value) for value in node.values]}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return {'operator':'NOT','operands':[graph(node.operand)]}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.upper() == 'JOIN':
            if (node.keywords or not 2 <= len(node.args) <= 9
                    or not isinstance(node.args[0], ast.Name) or node.args[0].id != 'N'):
                raise ValueError('JOIN requires JOIN(N, boolean operands...) with 1..8 operands and model parameter N.')
            join_sizes.append(len(node.args) - 1)
            return {'operator':'JOIN', 'count_parameter':'N', 'operands':[graph(value) for value in node.args[1:]]}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.upper() in arities and not node.keywords:
            operation = node.func.id.upper()
            lower, upper = arities[operation]
            if not lower <= len(node.args) <= upper:
                raise ValueError('Boolean operator has the wrong number of inputs: ' + operation)
            return {'operator':operation,'operands':[graph(value) for value in node.args]}
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            return {'operator':'XNOR' if isinstance(node.ops[0], ast.Eq) else 'XOR',
                    'operands':[graph(node.left),graph(node.comparators[0])]}
        raise ValueError('Only explicit Boolean names, AND/OR/NOT and supported decision operators are permitted.')
    tree = graph(parsed.body)
    if not 1 <= len(names) <= 8:
        raise ValueError('A fully verified Boolean decision requires 1..8 named inputs.')
    if bindings is not None and (set(bindings) != names or any(row.get('type') != 'boolean' for row in bindings.values())):
        raise ValueError('Boolean rule names must match explicitly Boolean signal bindings exactly.')
    result = {'expression':normalized,'tree':tree,'inputs':sorted(names),'output_type':'boolean','stateful':False}
    if join_sizes:
        result['parameter_schema'] = {'N':{'type':'number', 'required':True, 'unit':'dimensionless',
                                            'minimum':0, 'maximum':min(join_sizes), 'multipleOf':1}}
    return result


def validate_logic_cases(definition, cases):
    """Require complete independently supplied vectors, without calculating a second output."""
    from itertools import product
    rule = definition.get('logic_rule')
    if not rule:
        return
    parsed = inspect_logic_expression(rule['expression'])
    if rule != parsed:
        raise ValueError('Stored Boolean graph differs from its explicit expression.')
    inputs = parsed['inputs']
    schema = parsed.get('parameter_schema', {})
    observed = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('Boolean verification cases must be objects.')
        parameter_values = case.get('parameter_values', {})
        if schema:
            count = parameter_values.get('N') if isinstance(parameter_values, dict) else None
            if (not isinstance(parameter_values, dict) or set(parameter_values) != {'N'}
                    or type(count) not in (int, float) or not math.isfinite(count)
                    or count % 1 != 0 or not 0 <= count <= schema['N']['maximum']):
                raise ValueError('JOIN verification requires an explicit valid integer model parameter N in each case.')
        elif parameter_values:
            raise ValueError('This Boolean decision has no model parameters.')
        for step in case.get('steps') or []:
            if not isinstance(step, dict):
                raise ValueError('Boolean verification steps must be objects.')
            values = step.get('inputs')
            if not isinstance(values, dict) or set(values) != set(inputs) or any(type(value) is not bool for value in values.values()):
                raise ValueError('Boolean verification requires actual True/False inputs, no numeric truthiness.')
            if type(step.get('expected')) is not bool:
                raise ValueError('Boolean verification requires a Boolean expected output.')
            vector = tuple(values[name] for name in inputs)
            observed.add((count, vector) if schema else vector)
    required = set(product((False,True), repeat=len(inputs)))
    if schema:
        required = {(count, vector) for count in range(schema['N']['maximum'] + 1) for vector in required}
    if observed != required:
        raise ValueError('Boolean verification must cover its complete truth table.')


class QwenFunctionBlock(FunctionBlock):
    """One immutable source revision and one isolated ECU/function state."""
    def __init__(self, definition: dict):
        source = definition.get('source_code')
        if not isinstance(source, str) or not source or len(source.encode()) > 16384:
            raise ValueError('Function code must contain 1..16384 UTF-8 bytes.')
        self.source_sha256 = hashlib.sha256(source.encode()).hexdigest()
        expected = definition.get('source_sha256')
        if expected is not None and expected != self.source_sha256:
            raise ValueError('Function code revision/hash differs from the reviewed source.')
        self.definition = deepcopy(definition)
        self.schema = self.definition.get('parameter_schema') or {}
        if not isinstance(self.schema, dict) or len(self.schema) > 64:
            raise ValueError('Invalid function parameter contract.')
        for key, rule in self.schema.items():
            if not key.isidentifier() or not isinstance(rule, dict) or rule.get('type') not in {'number', 'boolean'}:
                raise ValueError('Invalid function parameter type.')
            if not isinstance(rule.get('unit'), str) or not rule['unit']:
                raise ValueError('Function parameter unit is required.')
            for bound in ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum'):
                if bound in rule and type(_finite(rule[bound])) is bool:
                    raise ValueError('Parameter bounds must be numeric.')
            if 'multipleOf' in rule and (rule['type'] != 'number' or type(_finite(rule['multipleOf'])) is bool or rule['multipleOf'] <= 0):
                raise ValueError('Parameter multipleOf must be a positive finite number.')
        tree = ast.parse(source)
        nodes = list(ast.walk(tree))
        if len(nodes) > 1024 or any(not isinstance(node, _ALLOWED) for node in nodes):
            raise ValueError('Unsupported or excessive function code syntax.')
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.ClassDef):
            raise ValueError('Exactly one FunctionBlock class is required.')
        cls = tree.body[0]
        if (not cls.name.isidentifier() or cls.name.startswith('_') or cls.decorator_list or cls.keywords
                or len(cls.bases) != 1 or not isinstance(cls.bases[0], ast.Name) or cls.bases[0].id != 'FunctionBlock'):
            raise ValueError('Function code must inherit the NIS FunctionBlock contract.')
        body = [n for n in cls.body if not self._docstring(n)]
        if len(body) != 1 or not isinstance(body[0], ast.FunctionDef):
            raise ValueError('FunctionBlock requires exactly one step method.')
        method = body[0]
        if (method.name != 'step' or method.decorator_list or method.returns or method.args.defaults
                or method.args.kw_defaults or method.args.kwonlyargs or method.args.vararg or method.args.kwarg
                or method.args.posonlyargs or [a.arg for a in method.args.args] != ['self', 'inputs', 'parameters', 'dt']
                or any(a.annotation for a in method.args.args)):
            raise ValueError('Required method: step(self, inputs, parameters, dt).')
        self._body = [n for n in method.body if not self._docstring(n)]
        self.name = cls.name
        for node in nodes:
            if isinstance(node, ast.Attribute) and not self._safe_attribute(node):
                raise ValueError('Function code attribute access is not permitted.')
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Attribute)
                    or node.func.attr != 'get' or not 1 <= len(node.args) <= 2 or node.keywords):
                raise ValueError('Only dictionary.get calls are permitted.')
            if isinstance(node, ast.Name) and node.id.startswith('_'):
                raise ValueError('Private names are not permitted.')
            if isinstance(node, ast.Expr) and not self._docstring(node):
                raise ValueError('Function code expression statements are not permitted.')
            if isinstance(node, ast.Assign):
                if len(node.targets) != 1 or not self._safe_target(node.targets[0]):
                    raise ValueError('Only local variables and literal self.state keys may be assigned.')
            if isinstance(node, ast.Constant):
                if isinstance(node.value, str):
                    if len(node.value) > 1000:
                        raise ValueError('Function code string exceeds limit.')
                elif node.value is not None:
                    _finite(node.value)
        self.logic_inputs = None
        if self.definition.get('logic_rule'):
            rule = inspect_logic_expression(self.definition['logic_rule']['expression'])
            if rule != self.definition['logic_rule'] or self.schema != rule.get('parameter_schema', {}):
                raise ValueError('Boolean decisions require their exact graph and explicit model parameter contract.')
            forbidden = {'dt'} if self.schema else {'dt','parameters'}
            if any(self._state(node) or isinstance(node, ast.Name) and node.id in forbidden for node in nodes):
                raise ValueError('Boolean decision code must be stateless and independent of time and undeclared parameters.')
            if self.schema:
                for node in nodes:
                    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'parameters'
                            and (not isinstance(node.slice, ast.Constant) or node.slice.value != 'N')):
                        raise ValueError('JOIN may read only the model parameter N.')
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'parameters'
                            and (not isinstance(node.args[0], ast.Constant) or node.args[0].value != 'N')):
                        raise ValueError('JOIN may read only the model parameter N.')
            self.logic_inputs = tuple(rule['inputs'])
        self.state: dict[str, float | bool] = {}

    @staticmethod
    def _docstring(node):
        return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)

    @staticmethod
    def _state(node):
        return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'state'

    @classmethod
    def _safe_attribute(cls, node):
        return cls._state(node) or (node.attr == 'get' and (
            isinstance(node.value, ast.Name) and node.value.id in {'inputs', 'parameters'} or cls._state(node.value)))

    @classmethod
    def _safe_target(cls, node):
        if isinstance(node, ast.Name):
            return node.id not in {'self', 'inputs', 'parameters', 'dt', 'FunctionBlock'} and not node.id.startswith('_')
        return (isinstance(node, ast.Subscript) and cls._state(node.value)
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)
                and 0 < len(node.slice.value) <= 80 and not node.slice.value.startswith('_'))

    def reset(self):
        self.state.clear()

    def validate_parameters(self, parameters):
        if not isinstance(parameters, dict) or len(parameters) > 64 or set(parameters) - set(self.schema):
            raise ValueError('Function parameters must match the declared contract.')
        parameters = {str(k): _finite(v) for k, v in parameters.items()}
        for key, rule in self.schema.items():
            if rule.get('required', True) and key not in parameters:
                raise ValueError('Required function parameter is missing: ' + key)
            if key not in parameters:
                continue
            value = parameters[key]
            if rule['type'] == 'boolean' and type(value) is not bool:
                raise ValueError('Boolean parameter required: ' + key)
            if rule['type'] == 'number' and type(value) is bool:
                raise ValueError('Numeric parameter required: ' + key)
            if 'multipleOf' in rule and value % rule['multipleOf'] != 0:
                raise ValueError('Function parameter requires the declared integer/multipleOf constraint: ' + key)
            if 'minimum' in rule and value < rule['minimum'] or 'maximum' in rule and value > rule['maximum']:
                raise ValueError('Function parameter outside declared range: ' + key)
            if 'exclusiveMinimum' in rule and value <= rule['exclusiveMinimum'] or 'exclusiveMaximum' in rule and value >= rule['exclusiveMaximum']:
                raise ValueError('Function parameter outside exclusive range: ' + key)
        relations = self.definition.get('parameter_relations') or []
        if not isinstance(relations, list) or len(relations) > 64:
            raise ValueError('Invalid declared parameter relations.')
        for rule in relations:
            if (not isinstance(rule, dict) or rule.get('left') not in parameters or rule.get('right') not in parameters
                    or rule.get('operator') not in {'<', '<=', '>', '>='}):
                raise ValueError('Invalid declared parameter relation.')
            operation = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge}[rule['operator']]
            if not operation(parameters[rule['left']], parameters[rule['right']]):
                raise ValueError('Function parameters violate their declared relation.')
        return parameters

    def step(self, inputs, parameters, dt):
        if not isinstance(inputs, dict) or len(inputs) > 64:
            raise ValueError('Function input count exceeds limit.')
        inputs = {str(k): _finite(v) for k, v in inputs.items()}
        if self.logic_inputs is not None and (set(inputs) != set(self.logic_inputs) or any(type(value) is not bool for value in inputs.values())):
            raise ValueError('Boolean decisions require exact True/False inputs, no implicit numeric truthiness.')
        parameters = self.validate_parameters(parameters)
        dt = _finite(dt)
        if type(dt) is bool or dt < 0:
            raise ValueError('Function dt must be finite and nonnegative.')
        env = {'inputs': inputs, 'parameters': parameters, 'dt': dt}
        state = dict(self.state)
        budget = [2048]

        def expr(node):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError('Function operation budget exceeded.')
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                return env[node.id]
            if self._state(node):
                return state
            if isinstance(node, ast.Subscript):
                return expr(node.value)[expr(node.slice)]
            if isinstance(node, ast.Call):
                container = expr(node.func.value)
                if not isinstance(container, dict):
                    raise ValueError('Function get target must be a dictionary.')
                return container.get(*(expr(a) for a in node.args))
            if isinstance(node, ast.BinOp):
                return _finite(_BINARY[type(node.op)](_finite(expr(node.left)), _finite(expr(node.right))))
            if isinstance(node, ast.UnaryOp):
                value = expr(node.operand)
                return not value if isinstance(node.op, ast.Not) else _finite(-value if isinstance(node.op, ast.USub) else +value)
            if isinstance(node, ast.Compare):
                left = expr(node.left)
                for operation, right in zip(node.ops, node.comparators):
                    right = expr(right)
                    if not _COMPARE[type(operation)](left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.BoolOp):
                result = None
                for child in node.values:
                    result = expr(child)
                    if isinstance(node.op, ast.And) and not result or isinstance(node.op, ast.Or) and result:
                        break
                return result
            if isinstance(node, ast.IfExp):
                return expr(node.body if expr(node.test) else node.orelse)
            raise ValueError('Unsupported function expression.')

        def statements(body):
            for node in body:
                budget[0] -= 1
                if budget[0] < 0:
                    raise ValueError('Function operation budget exceeded.')
                if isinstance(node, ast.Assign):
                    value = _finite(expr(node.value))
                    target = node.targets[0]
                    if isinstance(target, ast.Name):
                        env[target.id] = value
                    else:
                        state[target.slice.value] = value
                        if len(state) > 64:
                            raise ValueError('Function state limit exceeded.')
                elif isinstance(node, ast.Return):
                    return True, _finite(expr(node.value))
                elif isinstance(node, ast.If):
                    returned, value = statements(node.body if expr(node.test) else node.orelse)
                    if returned:
                        return True, value
                else:
                    raise ValueError('Unsupported function statement.')
            return False, None

        returned, value = statements(self._body)
        if not returned:
            raise ValueError('Function code must return a value on every executed path.')
        if self.logic_inputs is not None and type(value) is not bool:
            raise ValueError('Boolean decision must return a Boolean value.')
        self.state = state
        return BlockResult(value, dict(state), self.source_sha256)


def validate_function_spec(parameters: dict, signals: dict | None = None) -> QwenFunctionBlock:
    """One contract shared by proposal review, preflight and frozen execution."""
    definition = parameters.get('function_block')
    if not isinstance(definition, dict):
        raise ValueError('QWEN function definition is missing.')
    provenance = definition.get('provenance') or {}
    if (provenance.get('generated_by') != 'QWEN' or provenance.get('provider') != 'ollama-local'
            or not str(provenance.get('model', '')).lower().startswith('qwen')
            or not provenance.get('model_digest') or not provenance.get('request_sha256')
            or not definition.get('source_sha256')):
        raise ValueError('Local QWEN authorship and exact source revision are required.')
    block = QwenFunctionBlock(definition)
    block.validate_parameters(parameters.get('block_parameters'))
    bindings = parameters.get('transport_inputs')
    if not isinstance(bindings, dict) or not 1 <= len(bindings) <= 32:
        raise ValueError('Function code requires 1..32 explicitly bound inputs.')
    if definition.get('logic_rule'):
        inspect_logic_expression(definition['logic_rule']['expression'], bindings)
    declared = set()
    for node in ast.walk(ast.parse(definition['source_code'])):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'inputs'
                and isinstance(node.slice, ast.Constant)):
            declared.add(node.slice.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'inputs'
                and node.args and isinstance(node.args[0], ast.Constant)):
            declared.add(node.args[0].value)
    if declared != set(bindings):
        raise ValueError('Code inputs must match the reviewed signal bindings exactly.')
    for name, policy in bindings.items():
        if (not isinstance(name, str) or not name.isidentifier() or name.startswith('_')
                or not isinstance(policy, dict) or not policy.get('signal_id')
                or policy.get('type') not in {'number', 'boolean'}
                or not isinstance(policy.get('unit'), str) or policy.get('on_stale') not in {'hold', 'fallback'}):
            raise ValueError('Each function input needs canonical identity, type, unit and stale policy.')
        age = _finite(policy.get('max_age_ms'))
        if type(age) is bool or age < 0:
            raise ValueError('Input maximum age must be explicit and nonnegative.')
        value = _finite(policy.get('fallback'))
        if policy['type'] == 'boolean' and type(value) is not bool:
            raise ValueError('Boolean fallback is required for a boolean input.')
        if signals is not None:
            source = signals.get(str(policy['signal_id']))
            if source is None:
                raise ValueError('Function input does not exist in the project snapshot.')
            unit = source.get('unit') if isinstance(source, dict) else source.unit
            if definition.get('logic_rule'):
                row = source if isinstance(source, dict) else vars(source)
                minimum = row.get('min_value', row.get('minimum'))
                maximum = row.get('max_value', row.get('maximum'))
                if not (minimum is not None and maximum is not None and float(minimum) == 0 and float(maximum) == 1
                        and (str(row.get('data_type', '')).lower() in {'bool','boolean'} or row.get('length_bits') == 1)):
                    raise ValueError('Boolean logic requires a canonical Boolean input; compare physical measurements explicitly first.')
            if (unit or '') != policy['unit']:
                raise ValueError('Input unit differs from its canonical signal; explicit conversion is required.')
    if parameters.get('on_invalid') not in {'hold_output', 'fallback'}:
        raise ValueError('An explicit invalid-input output policy is required.')
    _finite(parameters.get('invalid_output'))
    if definition.get('logic_rule') and type(parameters['invalid_output']) is not bool:
        raise ValueError('Boolean decision invalid output must be explicitly True/False.')
    verify_function_cases(definition, parameters['block_parameters'], bindings)
    return block


def verify_function_cases(definition, parameters, bindings):
    """Expected values supplied separately from QWEN generation, preserved for review."""
    cases = definition.get('verification_cases')
    if cases is None:
        if definition.get('logic_rule'):
            raise ValueError('Boolean decisions require complete independent truth table cases.')
        return  # Low-level scalar fixtures/legacy drafts; proposal service requires cases.
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError('Function verification requires 1..32 independent cases.')
    validate_logic_cases(definition, cases)
    QwenFunctionBlock(definition).validate_parameters(parameters)
    checks = []
    for case in cases:
        if not isinstance(case, dict) or not case.get('source') or str(case['source']).lower().startswith('qwen'):
            raise ValueError('Expected behavior needs an independent source.')
        sequence = case.get('steps')
        if not isinstance(sequence, list) or not 1 <= len(sequence) <= 256:
            raise ValueError('Each verification sequence requires 1..256 steps.')
        instance = QwenFunctionBlock(definition)
        case_parameters = case.get('parameter_values', parameters) if definition.get('logic_rule', {}).get('parameter_schema') else parameters
        for step in sequence:
            inputs = step.get('inputs')
            if not isinstance(inputs, dict) or set(inputs) != set(bindings):
                raise ValueError('Verification inputs differ from reviewed bindings.')
            expected = _finite(step.get('expected'))
            actual = instance.step(inputs, case_parameters, step.get('dt_s')).value
            tolerance = _finite(step.get('tolerance', 0))
            if tolerance < 0 or (type(expected) is bool and (type(actual) is not bool or actual != expected)) or abs(actual - expected) > tolerance:
                raise ValueError('Function code failed independent case: ' + str(case.get('name', 'unnamed')))
        checks.append({'name':case.get('name'), 'source':case['source'], 'status':'PASSED', 'steps':len(sequence)})
    return checks


class EcuRuntime:
    """Run-local instances; generated code only sees bounded value dictionaries."""
    def __init__(self):
        self.instances = {}
        self.timestamps = {}
        self.outputs = {}
        self.revisions = {}

    def evaluate(self, ecu_id, signal_id, parameters, inputs, now, valid):
        key = (str(ecu_id), str(signal_id))
        revision = hashlib.sha256(json.dumps(parameters, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()
        if key in self.revisions and self.revisions[key] != revision:
            raise ValueError('Function revision cannot change during a frozen simulation run.')
        self.revisions[key] = revision
        block = self.instances.get(key)
        if block is None:
            block = self.instances[key] = validate_function_spec(parameters)
        previous = self.timestamps.get(key, now)
        if now < previous:
            raise ValueError('Function execution time must be monotonic.')
        dt = now - previous
        self.timestamps[key] = now
        if valid:
            result = block.step(inputs, parameters['block_parameters'], dt)
            value = result.value
            self.outputs[key] = value
            status = 'EVALUATED_SIMULATION_DESIGN'
        else:
            value = (self.outputs.get(key, parameters['invalid_output'])
                     if parameters['on_invalid'] == 'hold_output' else parameters['invalid_output'])
            status = 'INVALID_INPUT_' + parameters['on_invalid'].upper()
        return value, {'model':'QWEN_FUNCTION_BLOCK_V1', 'source_sha256':block.source_sha256,
            'block_name':block.name, 'state':dict(block.state), 'dt_s':dt, 'evaluation_s':now,
            'ecu_id':str(ecu_id), 'signal_id':str(signal_id), 'status':status,
            'parameters':dict(parameters['block_parameters']), 'input_valid':bool(valid)}
