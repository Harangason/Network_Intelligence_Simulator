"""Prepare guarded ownership moves from the current source, retaining algorithms."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/structure-completion-20261003'
GUARD = Path('F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py')
WRITES = {}


def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def write(path, content):
    WRITES[path] = content


def segment(source, node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
    return '\n'.join(source.splitlines()[start - 1:node.end_lineno])


def body(source, nodes):
    return textwrap.dedent('\n'.join(source.splitlines()[nodes[0].lineno - 1:nodes[-1].end_lineno]))


def node_named(source, name):
    return next(n for n in ast.parse(source).body if getattr(n, 'name', None) == name)


def replace_node(source, name, new):
    n = node_named(source, name)
    lines = source.splitlines()
    start = min([n.lineno] + [d.lineno for d in getattr(n, 'decorator_list', [])])
    return '\n'.join(lines[:start - 1]) + '\n' + new + '\n' + '\n'.join(lines[n.end_lineno:]) + '\n'


def function(name, arguments, code):
    return f'def {name}({arguments}):\n' + textwrap.indent(code, '    ') + '\n'


def apply(label):
    OUT.mkdir(parents=True, exist_ok=True)
    for path, content in WRITES.items():
        if path.endswith('.py'):
            ast.parse(content, filename=path)
    revisions = {}
    for path, new in WRITES.items():
        actual = ROOT / path
        revisions[path] = hashlib.sha256(actual.read_bytes()).hexdigest() if actual.is_file() else None
        if actual.is_file():
            before = OUT / 'before' / label / path
            before.parent.mkdir(parents=True, exist_ok=True)
            before.write_bytes(actual.read_bytes())
    workload = OUT / 'workload.json'
    if workload.exists():
        work = json.loads(workload.read_text())
    else:
        work = dict(goal_id='structure-completion-20261003', goal_type='STRUCTURE_COMPLETION',
                    repository=str(ROOT), project_scope='Canonical NIS structure migration',
                    requested_change='Close review findings R1-R5 and deliver verified production image',
                    kind='implementation', modify_code=True, allow_repair=True,
                    constraints=['Preserve identities, encodings and capabilities', 'Isolated SQL only',
                                 'Retain compatibility and historical campaign results'],
                    forbidden_changes=['Foreign technology defaults', 'Product database tests', 'Image pruning'],
                    required_outcomes=['registry_driven_frontend', 'technology_ownership', 'transition_evidence',
                                       'architecture_checker', 'module_documentation', 'production_delivery'],
                    validation_requirements=['targeted_regressions', 'behavior_equivalence', 'architecture',
                                             'full_release_gate', 'production_verification'],
                    unresolved_decisions=[], completion_status='IMPLEMENTING',
                    remaining_findings=['R1', 'R2', 'R3', 'R4', 'R5'], files_changed=[])
    work['revision_before'] = revisions
    work['files_changed'] = sorted(set(work['files_changed']) | set(WRITES))
    workload.write_text(json.dumps(work, indent=2), encoding='utf-8')
    result = subprocess.run([sys.executable, str(GUARD), 'before-apply', '--workload', str(workload)],
                            capture_output=True, text=True)
    (OUT / f'{label}-guard.json').write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout)
    for path, content in WRITES.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
    (OUT / f'{label}-files.json').write_text(json.dumps(sorted(WRITES), indent=2), encoding='utf-8')
    print(f'{label}: {len(WRITES)} guarded files written')


def prepare():
    calc = read('backend/nis/engineering/capacity/calculators.py')
    catalog = read('backend/nis/communication/catalog.py')
    tree = ast.parse(catalog)
    assignments = {n.targets[0].id: n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    values = {name: ast.literal_eval(assignments[name].value) for name in
              ['CAN_FD_DATA_LENGTHS', 'DDS_POLICY_ENTITIES', 'LOCAL_EVIDENCE_FIELDS', 'REVIEW_RATE_PROPOSALS']}
    techroot = 'backend/nis/communication/technologies/'
    for key, value in values['REVIEW_RATE_PROPOSALS'].items():
        metadata = {'rate_proposal': value}
        if key.upper() in values['LOCAL_EVIDENCE_FIELDS']:
            metadata['local_evidence_fields'] = values['LOCAL_EVIDENCE_FIELDS'][key.upper()]
        write(techroot + key + '/review.json', json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    write(techroot + 'can_fd/constants.py', '"""CAN FD DLC wire lengths; retained ISO frame contract."""\nCAN_FD_DATA_LENGTHS = ' + repr(values['CAN_FD_DATA_LENGTHS']) + '\n')
    write(techroot + 'dds/policies.py', '"""DDS QoS entity applicability, owned by DDS."""\nDDS_POLICY_ENTITIES = ' + repr(values['DDS_POLICY_ENTITIES']) + '\n')
    remove = ['CAN_FD_DATA_LENGTHS', 'DDS_POLICY_ENTITIES', 'LOCAL_EVIDENCE_FIELDS', 'REVIEW_RATE_PROPOSALS']
    lines = catalog.splitlines()
    for name in sorted(remove, key=lambda name: assignments[name].lineno, reverse=True):
        n = assignments[name]
        lines[n.lineno - 1:n.end_lineno] = []
    catalog = '\n'.join(lines) + '\n'
    projection = '''from json import loads
from pathlib import Path
from backend.nis.communication.technologies.can_fd.constants import CAN_FD_DATA_LENGTHS
from backend.nis.communication.technologies.dds.policies import DDS_POLICY_ENTITIES

def technology_review(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'review.json'
    return loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

REVIEW_RATE_PROPOSALS = {key: review['rate_proposal'] for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('rate_proposal')}
LOCAL_EVIDENCE_FIELDS = {key.upper(): tuple(map(tuple, review['local_evidence_fields']))
                         for key in TECHNOLOGY_IDS
                         if (review := technology_review(key)).get('local_evidence_fields')}
'''
    pos = catalog.index('\ndef technology_definitions')
    catalog = catalog[:pos] + '\n' + projection + catalog[pos:]
    write('backend/nis/communication/catalog.py', catalog)

    common = '"""Shared frame result and numeric contract; no technology formulas."""\nfrom __future__ import annotations\nfrom dataclasses import asdict, dataclass\nfrom math import isfinite\nfrom typing import Any\n\n'
    common += segment(calc, node_named(calc, 'FrameEstimate')) + '\n\n'
    common += segment(calc, node_named(calc, '_positive')) + '\n'
    write('backend/nis/communication/core/timing.py', common)
    estimate = node_named(calc, 'estimate_frame')
    branches = [n for n in estimate.body if isinstance(n, ast.If)]
    # Three generic guards, then the four existing concrete frame formulas.
    can_branch = next(n for n in branches if 'CAN_CLASSIC' in ast.unparse(n.test))
    fd_branch = next(n for n in branches if 'CANFD' in ast.unparse(n.test))
    eth_branch = next(n for n in branches if 'ETHERNET' in ast.unparse(n.test))
    lin_branch = next(n for n in branches if ast.unparse(n.test) == "normalized == 'LIN'")
    header = '"""Technology-owned frame and timing implementation; preserved calculation semantics."""\nfrom __future__ import annotations\nfrom math import ceil, isfinite\nfrom typing import Any\nfrom backend.nis.communication.core.timing import FrameEstimate, _positive\n\n'
    setup = 'normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")\npayload = max(0, int(payload_bytes))\nbitrate = _positive(parameters.get("bitrate"), 0.0)\nrate_confirmed = parameters.get("_rate_evidenced") is not False\navailable = bitrate > 0 and rate_confirmed\n'
    for key, branch in [('can', can_branch), ('can_fd', fd_branch), ('ethernet', eth_branch), ('lin', lin_branch)]:
        original = read(techroot + key + '/timing.py') if (ROOT / (techroot + key + '/timing.py')).exists() else ''
        source = header
        if key == 'can_fd':
            source += 'from .constants import CAN_FD_DATA_LENGTHS\n\n' + segment(calc, node_named(calc, 'can_fd_wire_data_bytes')) + '\n\n'
        if key == 'can':
            source += 'from backend.nis.communication.technologies.can_fd.timing import can_fd_wire_data_bytes\n\n'
        source += function('estimate_frame', 'protocol, payload_bytes, parameters', setup + body(calc, branch.body))
        if key == 'can':
            source += '\n' + segment(calc, node_named(calc, 'can_frame_time_bound_ms')) + '\n'
        if original:
            source += '\n' + original[original.index('from math import isfinite'):]
        write(techroot + key + '/timing.py', source)

    # Preserve the entire existing local evidence algorithm, specializing only
    # literal technology decisions; no protocol-specific rule stays in engineering.
    class Specialize(ast.NodeTransformer):
        def __init__(self, technology):
            self.technology = technology
        def visit_Name(self, node):
            if node.id == 'technology' and isinstance(node.ctx, ast.Load):
                return ast.copy_location(ast.Constant(self.technology), node)
            return node
        def constant(self, node):
            if all(isinstance(n, (ast.Expression, ast.Constant, ast.Set, ast.Tuple, ast.List,
                                  ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Not, ast.And, ast.Or,
                                  ast.Eq, ast.NotEq, ast.In, ast.NotIn, ast.Load)) for n in ast.walk(node)):
                return eval(compile(ast.Expression(node), '<literal decision>', 'eval'), {'__builtins__': {}})
            raise ValueError()
        def visit_If(self, node):
            node = self.generic_visit(node)
            try:
                return node.body if self.constant(node.test) else node.orelse
            except ValueError:
                return node
        def visit_IfExp(self, node):
            node = self.generic_visit(node)
            try:
                return node.body if self.constant(node.test) else node.orelse
            except ValueError:
                return node
    for key in ['i2c', 'spi']:
        evidence = Specialize(key.upper()).visit(ast.parse(segment(calc, node_named(calc, 'confirmed_serial_evidence'))))
        missing = Specialize(key.upper()).visit(ast.parse(segment(calc, node_named(calc, 'serial_evidence_missing_fields'))))
        ast.fix_missing_locations(evidence)
        ast.fix_missing_locations(missing)
        source = header + 'from backend.nis.communication.catalog import LOCAL_EVIDENCE_FIELDS, REVIEW_RATE_PROPOSALS\n\n'
        source += ast.unparse(evidence) + '\n\n' + ast.unparse(missing) + '\n\n'
        serial = '''normalized = str(protocol).upper()
payload = max(0, int(payload_bytes))
evidence = confirmed_serial_evidence(normalized, parameters, payload)
model = f"{normalized}_CONFIRMED_{'TRANSACTION' if normalized == 'I2C' else 'TRANSFER'}_BOUND_V1"
if evidence is None:
    return FrameEstimate(normalized, payload, 0, 0.0, model, is_generic_estimate=True, transmission_time_available=False)
bits = int(evidence['transfer_bits_bound'])
'''
        delay = ("delay_us = float(evidence['start_stop_bound_us']) + float(evidence['clock_stretch_limit_us']) + float(evidence.get('arbitration_bound_us') or 0) + (float(evidence['hs_entry_bound_us']) if evidence['i2c_mode']=='HIGH_SPEED' else 0)\n" if key == 'i2c'
                 else "delay_us = float(evidence['cs_setup_bound_us']) + float(evidence['inter_transfer_gap_us'])\n")
        source += function('estimate_frame', 'protocol, payload_bytes, parameters', serial + delay + "return FrameEstimate(normalized, payload, bits, bits / float(evidence['bitrate_bps']) + delay_us / 1_000_000, model)")
        write(techroot + key + '/timing.py', source)

    calc = replace_node(calc, 'FrameEstimate', 'from backend.nis.communication.core.timing import FrameEstimate, _positive')
    calc = replace_node(calc, '_positive', '')
    for name, args in [('confirmed_serial_evidence', 'protocol, parameters, payload_bytes=0'),
                       ('serial_evidence_missing_fields', 'protocol, parameters, payload_bytes=0')]:
        code = f'''from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
implementation = registry.timing_implementation(protocol)
handler = getattr(implementation, '{name}', None)
return handler(protocol, parameters, payload_bytes) if handler else {'None' if name.startswith('confirmed') else '[]'}'''
        calc = replace_node(calc, name, function(name, args, code))
    dispatch = '''normalized = str(protocol or 'CUSTOM').upper().replace('-', '_').replace(' ', '_')
payload = max(0, int(payload_bytes))
if normalized.lower() in DIRECT_IO_TECHNOLOGIES:
    return FrameEstimate(normalized, payload, 0, 0.0, 'DIRECT_IO_NO_FRAME',
                         is_generic_estimate=False, transmission_time_available=False)
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
implementation = registry.timing_implementation(protocol)
if implementation is not None:
    return implementation.estimate_frame(normalized, payload_bytes, parameters)
frame_bits = (payload + int(_positive(parameters.get('generic_overhead_bytes'), 24))) * 8
return FrameEstimate(normalized, payload, frame_bits, 0.0, 'GENERIC_ESTIMATE',
                     is_generic_estimate=True, transmission_time_available=False)'''
    calc = replace_node(calc, 'estimate_frame', function('estimate_frame', 'protocol: str, payload_bytes: int, parameters: dict[str, Any]', dispatch))
    calc = replace_node(calc, 'can_fd_wire_data_bytes', '')
    calc = replace_node(calc, 'can_frame_time_bound_ms', '')
    calc += '\nfrom backend.nis.communication.technologies.can_fd.timing import can_fd_wire_data_bytes\nfrom backend.nis.communication.technologies.can.timing import can_frame_time_bound_ms\n'
    write('backend/nis/engineering/capacity/calculators.py', calc)

    components = read('backend/nis/communication/core/components.py')
    timing_class = node_named(components, 'TechnologyTimingModel')
    method = next(n for n in timing_class.body if getattr(n, 'name', None) == 'transmission_time_us')
    initialization = next(n for n in method.body if isinstance(n, ast.If))
    native = next(n for n in method.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'native')
    lin_check = next(n for n in method.body if isinstance(n, ast.If) and ast.unparse(n.test) == "self.technology_id == 'lin'")
    for key in ['can', 'can_fd', 'ethernet', 'lin', 'i2c', 'spi']:
        code = 'technology_id = ' + repr(key) + '\n'
        if key in ['i2c', 'spi']:
            code += body(components, initialization.body).replace('self.technology_id', 'technology_id')
            code = code.replace('from backend.nis.engineering.capacity.calculators import confirmed_serial_evidence', '')
        elif key == 'can_fd':
            code += body(components, initialization.orelse[0].body)
        else:
            code += body(components, initialization.orelse[0].orelse)
        code += '\n' + segment(components, native).strip() + '\n'
        allowed = "{'can_frame_format'}" if key == 'can' else "{'can_fd_brs','can_frame_format','can_fd_dlc','can_fd_wire_data_bytes'}" if key == 'can_fd' else 'set()'
        code += f"if set(native) - {allowed}:\n    raise ValueError('CAN timing options are not applicable to this technology.')\n"
        code += 'rate_parameters.update(native)\nframe_parameters.update(native)\nreturn rate_parameters, frame_parameters'
        path = techroot + key + '/timing.py'
        args = 'payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None'
        WRITES[path] += '\n' + function('prepare_timing_parameters', args, code)
        if key == 'lin':
            WRITES[path] += '\n' + function('validate_timing_scope', 'payload_bytes, bitrate, rate_parameters, frame_parameters', body(components, lin_check.body))
        else:
            WRITES[path] += '\ndef validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):\n    return None\n'
    replacement = '''class TechnologyTimingModel:
    """Registry adapter; concrete framing and scope rules belong to technology owners."""
    def __init__(self, technology_id, profile):
        from importlib import import_module
        self.technology_id = technology_id
        self.profile = profile
        self.implementation = import_module(f'backend.nis.communication.technologies.{technology_id}.timing')

''' + textwrap.indent(function('transmission_time_us', 'self, payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None, technology_parameters=None',
'''rate_parameters, frame_parameters = self.implementation.prepare_timing_parameters(
    payload_bytes, bitrate, arbitration_bitrate=arbitration_bitrate, data_bitrate=data_bitrate,
    local_timing_evidence=local_timing_evidence, can_fd_brs=can_fd_brs, can_frame_format=can_frame_format,
    can_fd_dlc=can_fd_dlc, can_fd_wire_data_bytes=can_fd_wire_data_bytes)
''' + body(components, [next(n for n in method.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'technology_parameters is not None')]) + '''
self.implementation.validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters)
findings = TechnologyValidator(self.technology_id, self.profile).validate({'parameters': rate_parameters})
if findings:
    raise ValueError(findings[0].message)
frame = self.implementation.estimate_frame(self.technology_id, payload_bytes, frame_parameters)
if frame.is_generic_estimate or not frame.transmission_time_available:
    raise ValueError(f'{self.technology_id}: ausführbares Frame-Modell fehlt.')
return frame.transmission_time_s * 1_000_000'''), '    ')
    components = replace_node(components, 'TechnologyTimingModel', replacement)
    write('backend/nis/communication/core/components.py', components)
    registry = read('backend/nis/communication/registry.py')
    pos = registry.index('    def get_capabilities(')
    registry = registry[:pos] + '''    def timing_implementation(self, technology_id):
        """Resolve registered executable owner without an industry/technology fallback."""
        model = self._timing_models.get(self.normalize_id(technology_id))
        return getattr(model, 'implementation', None)

''' + registry[pos:]
    write('backend/nis/communication/registry.py', registry)

    # Shared queue management stays in simulation; CAN bus state and priority
    # selection are the existing algorithm, moved intact into CAN's owner.
    scheduler = read('backend/nis/simulation/runtime/event_scheduler.py')
    can_state = segment(scheduler, node_named(scheduler, '_CanBus'))
    # Include decorators when copying dataclasses.
    write(techroot + 'can/arbitration.py', '"""CAN release queues and CAN-ID arbitration; no inferred priority."""\nfrom dataclasses import dataclass, field\nimport heapq\nfrom backend.nis.simulation.simulation_cancellation import check_cancellation\n\n' + can_state + '''

def supports_event(event):
    return event.get('technology') in {'can', 'can_fd'}

def grant(bus, due):
    while bus.future and bus.future[0][0] <= due + 1e-12:
        check_cancellation()
        release, serial, event = heapq.heappop(bus.future)
        identifier = event.get('arbitration_id')
        priority = int(identifier) if identifier is not None else 0x20000000
        heapq.heappush(bus.ready, (priority, str(event['route_id']), release, serial, event))
    return heapq.heappop(bus.ready)[-1]
''')
    scheduler = replace_node(scheduler, '_CanBus', '')
    scheduler = scheduler.replace('@dataclass\n\n', '')
    scheduler = scheduler.replace('from dataclasses import dataclass, field', 'from dataclasses import dataclass\nfrom backend.nis.communication.technologies.can.arbitration import _CanBus, supports_event, grant')
    scheduler = scheduler.replace('event.get("technology") not in {"can", "can_fd"}', 'not supports_event(event)')
    start = scheduler.index('            while bus.future and bus.future[0][0] <= due + 1e-12:')
    end = scheduler.index('            self._active_bus = entry.network', start)
    scheduler = scheduler[:start] + scheduler[end:]
    scheduler = scheduler.replace('return heapq.heappop(bus.ready)[-1]', 'return grant(bus, due)')
    write('backend/nis/simulation/runtime/event_scheduler.py', scheduler)


if __name__ == '__main__':
    prepare()
    apply('technology-owners')

