import ast
import textwrap
from edit_utils import ROOT, read, write, extract, apply

path = 'backend/nis/traces/universal_trace.py'
source = read(path)
start = source.index("        if ethernet and technology['id'] == 'ethernet':")
end = source.index('        frame = estimate_frame(', start)
body = textwrap.dedent(source[start:end].split('\n', 1)[1])
owner_path = 'backend/nis/communication/technologies/ethernet/runtime.py'
owner = read(owner_path) + '\n\ndef apply_serializer_geometry(technology, ethernet, network_metadata, frame_parameters, payload_size, route):\n    if not ethernet or technology["id"] != "ethernet":\n        return\n' + textwrap.indent(body, '    ')
owner = owner.replace('from backend.nis.traces.trace_support', 'from backend.nis.communication.technologies.ethernet.transport import packet_bytes\nfrom backend.nis.traces.trace_support',1)
write(owner_path, owner)
source = source[:start] + '        apply_serializer_geometry(technology, ethernet, network_metadata, frame_parameters, payload_size, route)\n' + source[end:]
source = source.replace('import serialize_event as serialize_ethernet_event', 'import apply_serializer_geometry, serialize_event as serialize_ethernet_event')
old = "float(item.get('configured_cycle_ms') or 0) if item.get('technology') == 'lin' else 0"
source = source.replace(old, 'initial_release_priority(item)')
source = source.replace('import next_poll_start', 'import next_poll_start, initial_release_priority')
write('backend/nis/communication/technologies/lin/runtime.py', read('backend/nis/communication/technologies/lin/runtime.py') + '''

def initial_release_priority(event):
    return float(event.get('configured_cycle_ms') or 0) if event.get('technology') == 'lin' else 0
''')
write(path, source)

path = 'backend/nis/communication/technologies/ethernet/scheduling.py'
write(path, read(path) + '''

def independent_segment_key(network_id, segment_edges):
    return network_id, segment_edges

def serialized_path_factor(frame):
    return 2 if frame.calculation_model == 'ETHERNET_WIRE_ESTIMATE' else 1
''')
path = 'backend/nis/engineering/capacity/service.py'
source = read(path)
source = source.replace('        key = (network_id, segment_edges) if segment_protocol in {"ETHERNET", "AUTOMOTIVE_ETHERNET"} else (network_id, ())', "        scheduling = DEFAULT_TECHNOLOGY_REGISTRY.scheduling_implementation(segment_protocol)\n        key = getattr(scheduling, 'independent_segment_key', lambda network, edges: (network, ()))(network_id, segment_edges)")
source = source.replace('                ethernet = frame.calculation_model == "ETHERNET_WIRE_ESTIMATE"', "                scheduling = DEFAULT_TECHNOLOGY_REGISTRY.scheduling_implementation(segment_protocol)\n                path_factor = getattr(scheduling, 'serialized_path_factor', lambda frame: 1)(frame)\n                ethernet = path_factor == 2")
source = source.replace('(2 if ethernet else 1)', 'path_factor')

# Existing reserve and budget findings retain their exact text and severity.
start = source.index("            slot_load = schedule.get('slot_load_percent')")
end = source.index('            if schedule.get("status") not in', start)
reserve = textwrap.dedent(source[start:end])
source = source[:start] + '            findings.extend(lin_capacity_findings(network, sizing_policy, schedule))\n' + source[end:]
start = source.index('            schedule = network.get("lin_schedule") or {}')
end = source.index('            if network["target_status"]', start)
budget = textwrap.dedent(source[start:end])
source = source[:start] + source[end:]
write('backend/nis/communication/technologies/lin/assessment.py', '"""Existing LIN slot reserve and timing-budget findings."""\n\ndef capacity_findings(network, sizing_policy, schedule):\n    findings = []\n' + textwrap.indent(reserve + budget, '    ') + '    return findings\n')
source = source.replace('from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY', 'from backend.nis.communication.technologies.lin.assessment import capacity_findings as lin_capacity_findings\nfrom backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY',1)
start = source.index('            if route.get("e2e_timing_gap")')
end = source.index('            if not route.get("timing_verified")', start)
gap = textwrap.dedent(source[start:end])
write('backend/nis/communication/technologies/ethernet/assessment.py', '"""Existing switched Ethernet timing-evidence finding."""\n\ndef timing_gap_findings(route, _number):\n    findings = []\n' + textwrap.indent(gap, '    ') + '    return findings\n')
source = source[:start] + '            findings.extend(ethernet_timing_gap_findings(route, _number))\n' + source[end:]
source = source.replace('from backend.nis.communication.technologies.lin.assessment', 'from backend.nis.communication.technologies.ethernet.assessment import timing_gap_findings as ethernet_timing_gap_findings\nfrom backend.nis.communication.technologies.lin.assessment',1)
write(path, source)

# Replace nested imports of the deprecated shared native-format facade too.
common = ast.parse(read('backend/nis/traces/formats/common_trace.py'))
owners = {alias.asname or alias.name:(node.module,alias.name) for node in common.body if isinstance(node,ast.ImportFrom) for alias in node.names}
for path in (ROOT / 'backend/nis').rglob('*.py'):
    relative = path.relative_to(ROOT).as_posix()
    original = read(relative)
    current = source if relative == 'backend/nis/engineering/capacity/service.py' else (globals().get('unused','') or original)
    # Respect already queued edits.
    from edit_utils import WRITES
    current = WRITES.get(relative, original)
    lines = current.splitlines(keepends=True)
    nodes = [node for node in ast.walk(ast.parse(current)) if isinstance(node,ast.ImportFrom) and node.module == 'backend.nis.traces.formats.common_trace']
    for node in sorted(nodes,key=lambda n:n.lineno,reverse=True):
        groups = {}
        for alias in node.names:
            if alias.name not in owners:
                raise ValueError((relative,alias.name))
            module,name = owners[alias.name]
            groups.setdefault(module, []).append(name + (' as ' + alias.asname if alias.asname else ''))
        lines[node.lineno-1:node.end_lineno] = [' ' * node.col_offset + 'from ' + module + ' import ' + ', '.join(names) + '\n' for module,names in groups.items()]
    if nodes:
        write(relative, ''.join(lines))
apply('remaining-runtime-assessment-owners')
