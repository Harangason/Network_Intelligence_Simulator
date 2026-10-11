"""Guarded extraction of existing schedule algorithms into technology owners."""
from finish_structure_owners import *

techroot = 'backend/nis/communication/technologies/'
for key, names in {'can': ('CAN', 'CAN_CLASSIC'), 'can_fd': ('CAN_FD', 'CANFD'),
                   'ethernet': ('ETHERNET',), 'lin': ('LIN',), 'i2c': ('I2C',), 'spi': ('SPI',)}.items():
    path = techroot + key + '/timing.py'
    write(path, read(path) + '\nFRAME_PROTOCOLS = ' + repr(names) + '\n')
path = 'backend/nis/engineering/capacity/calculators.py'
write(path, read(path).replace('if implementation is not None:',
                             'if implementation is not None and normalized in implementation.FRAME_PROTOCOLS:'))

path = 'backend/nis/engineering/capacity/dimensioning.py'
source = read(path)
common = '"""Technology-neutral schedule constraints and numeric normalization."""\nfrom math import isfinite\n\n'
for name in ['number', '_constraints']:
    common += segment(source, node_named(source, name)) + '\n\n'
write('backend/nis/communication/core/scheduling.py', common)
schedule = node_named(source, 'bus_schedule')
branch = next(n for n in schedule.body if isinstance(n, ast.If) and ast.unparse(n.test) == "protocol in {'I2C', 'SPI'}")
lin = branch.orelse[0]
can = lin.orelse[0]
ethernet = can.orelse[0]
header = '"""Preserved technology-specific scheduling bound; functional acceptance remains separate."""\nfrom math import ceil, floor, lcm\nfrom backend.nis.communication.core.scheduling import number, _constraints\n\n'
for key, nodes in [('can', can.body), ('lin', lin.body)]:
    write(techroot + key + '/scheduling.py', header + function('schedule', 'rows, policy, periods, result', body(source, nodes) + '\nreturn result'))
write(techroot + 'can_fd/scheduling.py', '"""CAN FD uses the same CAN-ID completion bound as CAN CC."""\nfrom backend.nis.communication.technologies.can.scheduling import schedule\n')
eth = segment(source, node_named(source, '_ethernet_fifo_schedule')).replace('_ethernet_fifo_schedule', 'schedule', 1)
write(techroot + 'ethernet/scheduling.py', header + 'from collections import defaultdict\n\n' + eth)
for key in ['i2c', 'spi']:
    code = body(source, branch.body)
    code = code.replace('local_evidence_proposal(protocol, rows)', 'local_evidence_proposal(protocol, rows)')
    prelude = f"protocol = '{key.upper()}'\nfrom .timing import confirmed_serial_evidence\nfrom backend.nis.engineering.capacity.dimensioning import local_evidence_proposal\n"
    write(techroot + key + '/scheduling.py', header + function('schedule', 'rows, policy, periods, result', prelude + code + '\nreturn result'))

# The generic dispatcher has no bus-family formulas. Unsupported technologies
# keep the same explicit UNVERIFIED result and evidence-gap explanation.
default_nodes = ethernet.orelse
default_body = body(source, default_nodes)
gap_assign = next(n for n in default_nodes if isinstance(n, ast.Assign))
gaps = ast.literal_eval(gap_assign.value)
for key, message in gaps.items():
    review_path = techroot + key.lower() + '/review.json'
    value = json.loads(WRITES.get(review_path, read(review_path) if (ROOT / review_path).exists() else '{}'))
    value['schedule_evidence_gap'] = message
    write(review_path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
gap_code = segment(source, gap_assign)
default_body = default_body.replace(textwrap.dedent(gap_code), '')
# Dedent of the multiline assignment depends on source indentation; slicing
# its exact complete lines avoids leaving any family-specific message table.
default_body = body(source, default_nodes[1:])
default_body = default_body.replace("reason = evidence_gaps.get(", "reason = {protocol: technology_review(registry.normalize_id(protocol)).get('schedule_evidence_gap')}.get(")
# A missing metadata gap must use the original generic text rather than None.
default_body = default_body.replace("protocol,\n    f", "protocol,\n    f")
default_body = default_body.replace("reason = {protocol: technology_review(registry.normalize_id(protocol)).get('schedule_evidence_gap')}.get(\n    protocol,\n    f\"Für {protocol or 'dieses Protokoll'} ist noch kein deterministisches Scheduling-Modell hinterlegt.\",\n)",
                                   "reason = technology_review(registry.normalize_id(protocol)).get('schedule_evidence_gap') or f\"Für {protocol or 'dieses Protokoll'} ist noch kein deterministisches Scheduling-Modell hinterlegt.\"")
dispatch = '''from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.catalog import technology_review
from importlib import import_module
implementation = registry.timing_implementation(protocol)
if implementation is not None:
    handler = import_module(implementation.__package__ + '.scheduling').schedule
    if is_ethernet:
        result = handler(rows, result)
        if result['status'] != 'FEASIBLE_UNDER_ASSUMPTIONS':
            return result
    else:
        result = handler(rows, policy, periods, result)
        if result['status'] not in {'UNVERIFIED', 'FEASIBLE_UNDER_ASSUMPTIONS'} or not result['responses']:
            return result
else:
''' + textwrap.indent(default_body, '    ')
lines = source.splitlines()
lines[branch.lineno - 1:branch.end_lineno] = textwrap.indent(dispatch, '    ').splitlines()
source = '\n'.join(lines) + '\n'
source = replace_node(source, '_ethernet_fifo_schedule', 'from backend.nis.communication.technologies.ethernet.scheduling import schedule as _ethernet_fifo_schedule')
for name in ['number', '_constraints']:
    source = replace_node(source, name, '')
source = source.replace('VERSION = ', 'from backend.nis.communication.core.scheduling import number, _constraints\n\nVERSION = ', 1)
# Payload limits are canonical profile metadata, not a separate protocol table.
source = source.replace('limit = 8 if protocol in {"LIN", "CAN", "CAN_CLASSIC"} else 64 if protocol in {"CAN_FD", "CANFD"} else None',
'''try:
        profile_definition = DEFAULT_TECHNOLOGY_REGISTRY.profile(protocol)
    except KeyError:
        profile_definition = {}
    limit = profile_definition.get('max_payload_bytes') if profile_definition.get('family') != 'ETHERNET' else None''')
# Keep the historical Ethernet schedule classification explicit in dispatch.
write(path, source)
apply('technology-schedules')
