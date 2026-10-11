"""Separate native CAN demonstration generation from generic CLI orchestration."""
from strict_structure_utils import *

path = 'backend/nis/simulation/communication_generator.py'
source = read(path)
nodes = ast.parse(source).body
assignments = {n.targets[0].id:n for n in nodes if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
defs = {getattr(n,'name',None):n for n in nodes}
rate_owners = {'COMMON_NOMINAL_BITRATES':'can','CAN_FD_DATA_BITRATES':'can_fd','CAN_XL_DATA_BITRATES':'can_xl','ETHERNET_BITRATES':'ethernet'}
for constant, owner in rate_owners.items():
    options = ast.literal_eval(assignments[constant].value)
    write(f'backend/nis/communication/technologies/{owner}/export-options.json',json.dumps({'scope':'EXISTING_NATIVE_EXAMPLE_CLI_CHOICES','project_defaults':False,'choices':options},indent=2)+'\n')
write('backend/nis/communication/services/export_options.py','''"""Read existing technology-owned example CLI choices, never project defaults."""
import json
from pathlib import Path

def example_bitrate_choices(technology_id):
    """Project preserved demonstration choices without registering parameters."""
    path = Path(__file__).parents[1] / 'technologies' / technology_id / 'export-options.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['project_defaults'] is False
    return dict(data['choices'])
''')

# Preserve the native example's strict overflow behavior while sharing the same
# checksum implementation and keeping format contracts distinct from projects.
encoding_path = 'backend/nis/communication/technologies/can/encoding.py'
encoding = read(encoding_path)
encoding += '\n\n'+parts(source,['set_unsigned_le']).replace('def set_unsigned_le(', 'def set_unsigned_le_strict(')
encoding += '\n\n'+parts(source,['verify_payload_crc'])
write(encoding_path,encoding)

names = ['SignalDef','MessageDef','crc8_autosar','set_unsigned_le','get_unsigned_le','verify_payload_crc',
         'add_data_signals','add_response_signals','build_messages','encode_message_payload','encode_response_payload',
         'iter_scheduled_events','generate_blf','write_dbc','validate_blf']
implementations = [name for name in names if name not in ['crc8_autosar','set_unsigned_le','get_unsigned_le','verify_payload_crc']]
header = '''"""Existing CAN native example generation and mutable format records.

This preserves the standalone demonstration API; validated project generation
continues through the canonical registry and uses no demonstration defaults.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import can
from backend.nis.traces.trace_support import route_label
from backend.nis.traces.trace_realism import external_signal_records, physical_raw_value, signal_specs_for_message
from backend.nis.communication.technologies.can.encoding import crc8_autosar, get_unsigned_le, verify_payload_crc, set_unsigned_le_strict as set_unsigned_le
from backend.nis.communication.technologies.can.formats.trace_model import ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH, normalize_routing_row as normalized_routing_row
from backend.nis.industries.automotive.templates.trace_example import trace_example

DEFAULT_ROUTING_ROWS = [{key:row[key] for key in ('sender','receiver','cycle_ms','channel','gateway_to_channel','frame_id','name')} for row in trace_example()['DEFAULT_ROUTING_ROWS']]
try:
    CanMessage, BLFReader, BLFWriter = can.Message, can.BLFReader, can.BLFWriter
except AttributeError:
    from can.message import Message as CanMessage
    from can.io.blf import BLFReader, BLFWriter

'''
write('backend/nis/communication/technologies/can/formats/native_example.py', header+parts(source,implementations))
imports = ('from backend.nis.communication.technologies.can.formats.native_example import '+', '.join(implementations)+', CanMessage, BLFReader, BLFWriter\n'
           'from backend.nis.communication.technologies.can.encoding import crc8_autosar, get_unsigned_le, verify_payload_crc, set_unsigned_le_strict as set_unsigned_le')
new = without(source,set(names),imports)

# Remove the old writer import initialization, now owned by native_example.
new_lines = new.splitlines(keepends=True)
for n in reversed(ast.parse(new).body):
    if isinstance(n,ast.Try) and any(isinstance(v,ast.Name) and v.id=='CanMessage' for v in ast.walk(n)):
        new_lines[n.lineno-1:n.end_lineno]=[]
new = ''.join(new_lines)
lines = new.splitlines(keepends=True)
for n in reversed(ast.parse(new).body):
    if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name):
        name=n.targets[0].id
        if name in rate_owners:
            lines[n.lineno-1:n.end_lineno]=[f"{name} = example_bitrate_choices('{rate_owners[name]}')\n"]
        elif name in {'ROUTE_INFO_START_BYTE','ROUTE_INFO_LENGTH','DEFAULT_ROUTING_ROWS'}:
            lines[n.lineno-1:n.end_lineno]=[]
new = ''.join(lines)
new = new.replace('import can\n', 'from backend.nis.communication.services.export_options import example_bitrate_choices\nfrom backend.nis.communication.technologies.can.formats.native_example import DEFAULT_ROUTING_ROWS\nfrom backend.nis.communication.technologies.can.formats.trace_model import ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH\n')
write(path,new)

mdf_path='backend/nis/traces/formats/mdf_writer.py'
write('backend/nis/communication/technologies/can/formats/mdf_writer.py',read(mdf_path))
write(mdf_path,'"""Compatibility export: this writer records CAN signals, not a neutral MDF model."""\nfrom backend.nis.communication.technologies.can.formats.mdf_writer import write_mdf\n')
for candidate in (ROOT/'backend/nis').rglob('*.py'):
    relative=candidate.relative_to(ROOT).as_posix()
    if relative==mdf_path:continue
    text=WRITES.get(relative,read(relative))
    if 'from backend.nis.traces.formats.mdf_writer import' in text:
        write(relative,text.replace('from backend.nis.traces.formats.mdf_writer import','from backend.nis.communication.technologies.can.formats.mdf_writer import'))
apply('native-generator-owners')
