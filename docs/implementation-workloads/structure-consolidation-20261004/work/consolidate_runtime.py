"""Move existing technology algorithms without changing their event contracts."""
import ast
import textwrap
from edit_utils import read, write, extract, apply

path = 'backend/nis/traces/universal_trace.py'
source = read(path)
names = {'_restbus_settings', '_reverse_flow', '_restbus_control_event', '_add_restbus_sessions', '_restbus_ack_events'}
chunk, source = extract(source, names)
write('backend/nis/communication/technologies/ethernet/restbus.py',
      '"""Existing Ethernet restbus session and acknowledgement behavior."""\nfrom __future__ import annotations\nfrom typing import Any\nimport hashlib\nfrom backend.nis.communication.technologies.ethernet.transport import wire_bytes\n\n' + chunk)
source = source.replace('def _interface_index(', 'from backend.nis.communication.technologies.ethernet.restbus import (' + ', '.join(sorted(names)) + ')\n\ndef _interface_index(', 1)
tree = ast.parse(source)
serializer = next(n for n in tree.body if getattr(n, 'name', '') == '_serialize_event')
branch = next(n for n in serializer.body if isinstance(n, ast.If) and ast.unparse(n.test) == "event.get('ethernet')")
lines = source.splitlines(keepends=True)
body = textwrap.dedent(''.join(lines[branch.body[0].lineno-1:branch.end_lineno]))
owner = '"""Ethernet full-duplex port queues and runtime load measurement."""\nfrom backend.nis.traces.trace_support import iso_utc as _utc\n\ndef serialize_event(event, config, trace_start, port_available_at, requested_at, network_id, transmission_s):\n' + textwrap.indent(body, '    ')
load_path = 'backend/nis/simulation/port_load.py'
owner += '\n\n' + read(load_path).replace('"""Ethernet occupancy is measured per full-duplex port, not across a fake bus."""', '')
write('backend/nis/communication/technologies/ethernet/runtime.py', owner)
lines[branch.lineno-1:branch.end_lineno] = ['    if event.get("ethernet"):\n', '        return serialize_ethernet_event(event, config, trace_start, port_available_at, requested_at, network_id, transmission_s)\n']
source = ''.join(lines)
old = '''        period_s, offset_s = float(slot["period_ms"]) / 1000, float(slot["offset_ms"]) / 1000
        transmit_start = offset_s + max(0, ceil((transmit_start - offset_s) / period_s - 1e-9)) * period_s'''
assert old in source
source = source.replace(old, '        transmit_start = next_poll_start(transmit_start, slot)')
source = source.replace('def _serialize_event(', 'from backend.nis.communication.technologies.ethernet.runtime import serialize_event as serialize_ethernet_event\nfrom backend.nis.communication.technologies.lin.runtime import next_poll_start\n\ndef _serialize_event(', 1)
write('backend/nis/communication/technologies/lin/runtime.py', '''"""LIN poll-slot alignment for the existing simulated schedule."""
from math import ceil

def next_poll_start(transmit_start, slot):
    period_s, offset_s = float(slot["period_ms"]) / 1000, float(slot["offset_ms"]) / 1000
    return offset_s + max(0, ceil((transmit_start - offset_s) / period_s - 1e-9)) * period_s
''')
write(path, source)
write(load_path, '"""Compatibility export for the Ethernet runtime owner."""\nfrom backend.nis.communication.technologies.ethernet.runtime import ethernet_port_load\n')

# The historical mutable generator exports retain dictionary insertion order.
path = 'backend/nis/simulation/communication_generator.py'
chunk, source = extract(read(path), {'normalized_routing_row'})
# Both historical normalizers have identical values; this adapter preserves order.
write('backend/nis/communication/technologies/can/formats/routing.py', '''"""CAN native-example routing compatibility contract."""
from backend.nis.communication.technologies.can.formats.trace_model import normalize_routing_row

def normalized_routing_row(row, index, channel_count):
    normalized = normalize_routing_row(row, index, channel_count)
    keys = ('sender', 'receiver', 'cycle_ms', 'channel', 'gateway_to_channel', 'frame_id', 'name')
    return {**{key: normalized[key] for key in keys}, **{key: value for key, value in normalized.items() if key not in keys}}
''')
write(path, source.replace('def load_routing_table(', 'from backend.nis.communication.technologies.can.formats.routing import normalized_routing_row\n\ndef load_routing_table(', 1))
path = 'backend/nis/communication/technologies/can/formats/native_example.py'
write(path, read(path).replace(', normalize_routing_row as normalized_routing_row', '') + '\nfrom backend.nis.communication.technologies.can.formats.routing import normalized_routing_row\n')
apply('runtime-owners')
