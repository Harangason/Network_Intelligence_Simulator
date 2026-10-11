"""Move existing native trace implementations to their actual protocol owners."""
from strict_structure_utils import *

common_path = 'backend/nis/traces/formats/common_trace.py'
source = read(common_path)
tree = ast.parse(source)
assignments = {node.targets[0].id: node for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
def assignment(name):
    return segment(source,assignments[name])

neutral = ['utc_now','iso_utc','route_label','safe_identifier','parse_optional_int','triangle_wave','write_text']
write('backend/nis/traces/trace_support.py', '"""Technology-neutral trace timestamps, identifiers and text output."""\nfrom __future__ import annotations\nimport re\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\n' + parts(source,neutral))

fixtures = {name: ast.literal_eval(assignments[name].value) for name in ['COMMUNICATION_PAIRS','DEFAULT_ROUTING_ROWS','ETHERNET_NODES']}
write('backend/nis/industries/automotive/templates/trace-example.json',json.dumps(fixtures,indent=2)+'\n')
write('backend/nis/industries/automotive/templates/trace_example.py', '''"""Preserved Automotive demonstration data; never project transport defaults."""
import json
from pathlib import Path

def trace_example():
    """Return a fresh example so callers cannot mutate the shared definition."""
    return json.loads(Path(__file__).with_name('trace-example.json').read_text(encoding='utf-8'))
''')

encoding = ['crc8_autosar','set_unsigned_le','get_unsigned_le']
write('backend/nis/communication/technologies/can/encoding.py', '"""Preserved CAN example checksum and bit packing contracts."""\nfrom __future__ import annotations\n\n' + parts(source,encoding))

can_names = ['SignalDef','MessageDef','CanFrame','normalize_routing_row','load_routing_table','write_routing_template',
             'data_signals','response_signals','build_messages','encode_data_payload','encode_response_payload','iter_schedule','build_can_trace']
can_header = '''"""CAN native format trace models and preserved deterministic demonstration generator.

These format records are not a second engineering project model. Demonstration
traffic is separate from validated, project-bound simulation and capacity.
"""
from __future__ import annotations
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from backend.nis.traces.trace_support import utc_now, route_label, safe_identifier, parse_optional_int
from backend.nis.traces.trace_realism import external_signal_records, physical_raw_value, signal_specs_for_message
from backend.nis.industries.automotive.templates.trace_example import trace_example
from backend.nis.communication.technologies.can.encoding import crc8_autosar, set_unsigned_le, get_unsigned_le

ROUTE_INFO_START_BYTE = 20
ROUTE_INFO_LENGTH = 44
DEFAULT_ROUTING_ROWS = trace_example()['DEFAULT_ROUTING_ROWS']

'''
write('backend/nis/communication/technologies/can/formats/trace_model.py',can_header+parts(source,can_names))

someip_names = ['build_someip_payload','someip_payload_text']
someip_constants = ['SOMEIP_REQUEST','SOMEIP_REQUEST_NO_RETURN','SOMEIP_NOTIFICATION','SOMEIP_RESPONSE']
write('backend/nis/communication/technologies/someip/encoding.py', '"""Existing SOME/IP header encoder and native trace example payloads."""\nfrom __future__ import annotations\nimport struct\nfrom backend.nis.traces.trace_support import route_label\n\n' + '\n'.join(assignment(n) for n in someip_constants)+'\n\n'+parts(source,someip_names))
write('backend/nis/communication/technologies/someip_sd/constants.py','"""Existing SOME/IP service discovery identifiers used by trace adapters."""\n'+assignment('SOMEIP_SD_SERVICE_ID')+'\n'+assignment('SOMEIP_SD_METHOD_ID')+'\n')

write('backend/nis/communication/technologies/ip/encoding.py', '"""Existing IPv4 address and Internet checksum encoding used by native exports."""\nimport struct\n\n'+parts(source,['ip_bytes','internet_checksum']))
eth_names = ['EthernetFrame','mac_bytes','build_udp_ipv4_ethernet_packet','make_ethernet_frame','build_ethernet_trace']
eth_header = '''"""Preserved Ethernet/IPv4/UDP/SOME-IP native example trace adapter.

The protocol stack is explicit. This example writer supplies no project defaults
and makes no additional capacity or native transport support claim.
"""
from __future__ import annotations
import random
import struct
from dataclasses import dataclass
from backend.nis.traces.trace_support import utc_now
from backend.nis.industries.automotive.templates.trace_example import trace_example
from backend.nis.communication.technologies.ip.encoding import ip_bytes, internet_checksum
from backend.nis.communication.technologies.someip.encoding import build_someip_payload, someip_payload_text, SOMEIP_REQUEST, SOMEIP_REQUEST_NO_RETURN, SOMEIP_NOTIFICATION, SOMEIP_RESPONSE
from backend.nis.communication.technologies.someip_sd.constants import SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID

ETHERNET_NODES = {key:tuple(value) for key,value in trace_example()['ETHERNET_NODES'].items()}

'''
write('backend/nis/communication/technologies/ethernet/formats/trace_model.py',eth_header+parts(source,eth_names))

facade = '''"""Compatibility exports for native trace adapters.

Algorithms live with CAN, Ethernet, IP and SOME/IP. Only timestamps, identifiers
and technology-neutral text output belong to the shared trace layer.
"""
from backend.nis.traces.trace_support import '''+', '.join(neutral)+'\n'
facade += 'from backend.nis.communication.technologies.can.formats.trace_model import '+', '.join(can_names)+', ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH, DEFAULT_ROUTING_ROWS\n'
facade += 'from backend.nis.communication.technologies.can.encoding import '+', '.join(encoding)+'\n'
facade += 'from backend.nis.communication.technologies.ethernet.formats.trace_model import '+', '.join(eth_names)+', ETHERNET_NODES\n'
facade += 'from backend.nis.communication.technologies.ip.encoding import ip_bytes, internet_checksum\n'
facade += 'from backend.nis.communication.technologies.someip.encoding import '+', '.join(someip_names+someip_constants)+'\n'
facade += 'from backend.nis.communication.technologies.someip_sd.constants import SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID\n'
facade += "from backend.nis.industries.automotive.templates.trace_example import trace_example\nCOMMUNICATION_PAIRS = [tuple(pair) for pair in trace_example()['COMMUNICATION_PAIRS']]\n"
write(common_path,facade)

# Internal consumers import each owner directly; the old public facade remains.
owners = {name:'backend.nis.traces.trace_support' for name in neutral}
owners.update({name:'backend.nis.communication.technologies.can.formats.trace_model' for name in can_names+['ROUTE_INFO_START_BYTE','ROUTE_INFO_LENGTH','DEFAULT_ROUTING_ROWS']})
owners.update({name:'backend.nis.communication.technologies.can.encoding' for name in encoding})
owners.update({name:'backend.nis.communication.technologies.ethernet.formats.trace_model' for name in eth_names+['ETHERNET_NODES']})
owners.update({name:'backend.nis.communication.technologies.ip.encoding' for name in ['ip_bytes','internet_checksum']})
owners.update({name:'backend.nis.communication.technologies.someip.encoding' for name in someip_names+someip_constants})
owners.update({name:'backend.nis.communication.technologies.someip_sd.constants' for name in ['SOMEIP_SD_SERVICE_ID','SOMEIP_SD_METHOD_ID']})
for path in (ROOT/'backend/nis').rglob('*.py'):
    relative = path.relative_to(ROOT).as_posix()
    if relative == common_path: continue
    text = read(relative)
    nodes = [node for node in ast.parse(text).body if isinstance(node,ast.ImportFrom) and node.module=='backend.nis.traces.formats.common_trace']
    lines = text.splitlines(keepends=True)
    for node in reversed(nodes):
        groups = {}
        for item in node.names:
            assert item.name in owners,(relative,item.name)
            groups.setdefault(owners[item.name],[]).append(item.name + (' as '+item.asname if item.asname else ''))
        lines[node.lineno-1:node.end_lineno] = [f'from {owner} import {", ".join(names)}\n' for owner,names in groups.items()]
    if nodes: write(relative,''.join(lines))
apply('native-trace-owners')
